"""
Comprehensive test suite for Google Ads tracking endpoint
Tests edge cases, security, and production failure scenarios
"""
import json
import sys
import os
import time
from unittest.mock import Mock, patch, MagicMock
import pytest

# Set environment variables BEFORE importing anything
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'test-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret'
os.environ['DYNAMODB_TABLE_NAME'] = 'fraudguard-events-dev'
os.environ['ORCHESTRATOR_FUNCTION'] = 'fraudguard-orchestrator'
os.environ['FRAUD_THRESHOLD'] = '0.65'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock boto3 clients before importing
mock_lambda_client = MagicMock()
mock_dynamodb_resource = MagicMock()
mock_table = MagicMock()
mock_dynamodb_resource.Table.return_value = mock_table

with patch('boto3.client', return_value=mock_lambda_client), \
     patch('boto3.resource', return_value=mock_dynamodb_resource):
    from google_ads_tracking.app import (
        lambda_handler,
        validate_google_ads_params,
        sanitize_string,
        map_google_ads_to_event,
        create_error_response
    )


class MockContext:
    """Mock Lambda context"""
    def __init__(self):
        self.function_name = "GoogleAdsTrackingHandler"
        self.function_version = "$LATEST"
        self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:GoogleAdsTrackingHandler"
        self.memory_limit_in_mb = 1024
        self.aws_request_id = "test-request-id"
        self.log_group_name = "/aws/lambda/GoogleAdsTrackingHandler"
        self.log_stream_name = "test-stream"
        self.remaining_time_in_millis = lambda: 5000


class TestGoogleAdsTracking:
    """Test suite for Google Ads tracking endpoint"""
    
    def setup_method(self):
        """Reset mocks before each test"""
        mock_lambda_client.reset_mock()
        mock_table.reset_mock()
        mock_lambda_client.invoke.return_value = {
            'StatusCode': 202,
            'ResponseMetadata': {'HTTPStatusCode': 202}
        }
    
    # ========== VALIDATION TESTS ==========
    
    def test_valid_parameters(self):
        """Test valid Google Ads parameters"""
        params = {
            'cid': '123456789',
            'gclid': 'CjwKCAjw_xyz123abc456',
            'kw': 'buy shoes online',
            'aid': '987654321',
            'target': 'placement-123'
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is None
        assert validated['cid'] == '123456789'
        assert validated['gclid'] == 'CjwKCAjw_xyz123abc456'
    
    def test_missing_required_parameter(self):
        """Test missing required parameter (cid)"""
        params = {'gclid': 'CjwKCAjw_xyz123abc456'}
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert 'Missing required parameter: cid' in errors
    
    def test_invalid_parameter_pattern(self):
        """Test invalid parameter pattern (special characters)"""
        params = {
            'cid': '123456789',
            'gclid': 'invalid!@#$%'  # Invalid characters
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert any('does not match required pattern' in e for e in errors)
    
    def test_parameter_exceeds_max_length(self):
        """Test parameter exceeding max length"""
        params = {
            'cid': '123456789',
            'kw': 'a' * 201  # Exceeds max_length of 200
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert any('exceeds max length' in e for e in errors)
    
    def test_empty_string_vs_none(self):
        """Test empty string vs None handling"""
        # Empty string should be treated as missing for required params
        params = {'cid': ''}
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert 'Missing required parameter: cid' in errors
    
    def test_non_string_type(self):
        """Test non-string parameter type"""
        params = {
            'cid': 123456789,  # Integer instead of string
            'gclid': 'CjwKCAjw_xyz123abc456'
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert any('Invalid type' in e for e in errors)
    
    def test_unicode_characters(self):
        """Test Unicode character handling"""
        params = {
            'cid': '123456789',
            'kw': 'buy shoes 鞋子'  # Unicode characters
        }
        validated, errors = validate_google_ads_params(params)
        # Unicode should be allowed in sanitized fields
        assert errors is None or 'kw' in validated
    
    # ========== XSS/SECURITY TESTS ==========
    
    def test_xss_attempt_in_keyword(self):
        """Test XSS attempt in keyword (sanitized field)"""
        params = {
            'cid': '123456789',
            'kw': '<script>alert("XSS")</script>buy shoes'
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is None
        # Script tags should be removed
        assert '<script>' not in validated['kw']
        assert 'alert' in validated['kw']  # But content should remain
    
    def test_sql_injection_attempt(self):
        """Test SQL injection attempt (should be sanitized)"""
        params = {
            'cid': '123456789',
            'kw': "'; DROP TABLE events; --"
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is None
        # Single quotes should be removed
        assert "'" not in validated['kw']
    
    def test_path_traversal_attempt(self):
        """Test path traversal attempt"""
        params = {
            'cid': '123456789',
            'kw': '../../../etc/passwd'
        }
        validated, errors = validate_google_ads_params(params)
        # Should pass validation (not a security issue for DynamoDB)
        assert errors is None
    
    def test_html_entities(self):
        """Test HTML entities in parameters"""
        params = {
            'cid': '123456789',
            'kw': 'buy &amp; sell shoes'
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is None
        # HTML entities should be preserved (not dangerous)
    
    # ========== EDGE CASE TESTS ==========
    
    def test_null_query_string_parameters(self):
        """Test null queryStringParameters (API Gateway edge case)"""
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': None  # API Gateway can return None
        }
        context = MockContext()
        response = lambda_handler(event, context)
        # Should return 204 even with None params (graceful degradation)
        assert response['statusCode'] == 204
    
    def test_missing_query_string_parameters(self):
        """Test missing queryStringParameters key"""
        event = {
            'httpMethod': 'GET',
            'path': '/pt'
            # No queryStringParameters key
        }
        context = MockContext()
        response = lambda_handler(event, context)
        # Should return 204 (graceful degradation)
        assert response['statusCode'] == 204
    
    def test_empty_query_string_parameters(self):
        """Test empty queryStringParameters dict"""
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': {}
        }
        context = MockContext()
        response = lambda_handler(event, context)
        # Should return 400 (missing required cid)
        assert response['statusCode'] == 400
    
    def test_very_long_parameter_value(self):
        """Test very long parameter value (memory/DoS concern)"""
        params = {
            'cid': '123456789',
            'kw': 'a' * 10000  # Very long string
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert any('exceeds max length' in e for e in errors)
    
    def test_special_characters_in_pattern_fields(self):
        """Test special characters in pattern-validated fields"""
        params = {
            'cid': '123456789',
            'gclid': 'CjwKCAjw_xyz123abc456!@#'  # Special chars in pattern field
        }
        validated, errors = validate_google_ads_params(params)
        assert errors is not None
        assert any('does not match required pattern' in e for e in errors)
    
    # ========== LAMBDA HANDLER TESTS ==========
    
    def test_successful_request(self):
        """Test successful Google Ads tracking request"""
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': {
                'cid': '123456789',
                'gclid': 'CjwKCAjw_xyz123abc456',
                'kw': 'buy shoes online'
            }
        }
        context = MockContext()
        start_time = time.time()
        response = lambda_handler(event, context)
        elapsed_ms = (time.time() - start_time) * 1000
        
        assert response['statusCode'] == 204
        assert elapsed_ms < 1000  # Must be < 1 second
        assert 'Access-Control-Allow-Origin' in response['headers']
        # Verify async Lambda was invoked
        assert mock_lambda_client.invoke.called
    
    def test_response_time_requirement(self):
        """Test that response time is < 1 second (Google requirement)"""
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': {
                'cid': '123456789',
                'gclid': 'CjwKCAjw_xyz123abc456'
            }
        }
        context = MockContext()
        start_time = time.time()
        response = lambda_handler(event, context)
        elapsed_ms = (time.time() - start_time) * 1000
        
        assert elapsed_ms < 1000, f"Response time {elapsed_ms}ms exceeds 1s limit"
        assert response['statusCode'] == 204
    
    def test_error_returns_204(self):
        """Test that errors still return 204 (Google requirement)"""
        # Create an event that will cause an error
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': {
                'cid': None  # Invalid type
            }
        }
        context = MockContext()
        response = lambda_handler(event, context)
        # Even on error, should return 204 to avoid Google timeout
        assert response['statusCode'] == 204
    
    # ========== AWS INTEGRATION TESTS ==========
    
    def test_missing_dynamodb_table_name(self):
        """Test behavior when DYNAMODB_TABLE_NAME is not set"""
        original_table = os.environ.get('DYNAMODB_TABLE_NAME')
        os.environ.pop('DYNAMODB_TABLE_NAME', None)
        
        try:
            event = {
                'httpMethod': 'GET',
                'path': '/pt',
                'queryStringParameters': {
                    'cid': '123456789',
                    'gclid': 'CjwKCAjw_xyz123abc456'
                }
            }
            context = MockContext()
            response = lambda_handler(event, context)
            # Should still return 204 (graceful degradation)
            assert response['statusCode'] == 204
        finally:
            if original_table:
                os.environ['DYNAMODB_TABLE_NAME'] = original_table
    
    def test_missing_orchestrator_function(self):
        """Test behavior when ORCHESTRATOR_FUNCTION is not set"""
        original_func = os.environ.get('ORCHESTRATOR_FUNCTION')
        os.environ.pop('ORCHESTRATOR_FUNCTION', None)
        
        try:
            event = {
                'httpMethod': 'GET',
                'path': '/pt',
                'queryStringParameters': {
                    'cid': '123456789',
                    'gclid': 'CjwKCAjw_xyz123abc456'
                }
            }
            context = MockContext()
            response = lambda_handler(event, context)
            # Should still return 204 (graceful degradation)
            assert response['statusCode'] == 204
        finally:
            if original_func:
                os.environ['ORCHESTRATOR_FUNCTION'] = original_func
    
    def test_lambda_invoke_failure(self):
        """Test behavior when Lambda invoke fails"""
        mock_lambda_client.invoke.side_effect = Exception("Lambda invoke failed")
        
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': {
                'cid': '123456789',
                'gclid': 'CjwKCAjw_xyz123abc456'
            }
        }
        context = MockContext()
        response = lambda_handler(event, context)
        # Should still return 204 (error handled gracefully)
        assert response['statusCode'] == 204
    
    def test_dynamodb_put_failure(self):
        """Test behavior when DynamoDB put_item fails"""
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': {
                'cid': '123456789',
                'gclid': 'CjwKCAjw_xyz123abc456'
            }
        }
        context = MockContext()
        response = lambda_handler(event, context)
        # Should still return 204 (error handled gracefully)
        assert response['statusCode'] == 204
    
    # ========== EVENT MAPPING TESTS ==========
    
    def test_event_mapping_completeness(self):
        """Test that all Google Ads parameters are mapped correctly"""
        from datetime import datetime, timezone
        params = {
            'cid': '123456789',
            'gclid': 'CjwKCAjw_xyz123abc456',
            'kw': 'buy shoes',
            'aid': '987654321',
            'target': 'placement-123',
            'mt': 'search',
            'device': 'mobile',
            'creative': 'ad-456'
        }
        request_time = datetime.now(timezone.utc)
        event = map_google_ads_to_event(params, request_time)
        
        assert event['source'] == 'google_ads'
        assert event['event_type'] == 'click'
        assert event['gclid'] == 'CjwKCAjw_xyz123abc456'
        assert event['campaign_id'] == '123456789'
        assert event['ad_group_id'] == '987654321'
        assert event['keyword'] == 'buy shoes'
        assert event['target_id'] == 'placement-123'
        assert event['ip_address'] is None  # Not available in parallel tracking
        assert 'event_id' in event
        assert 'timestamp' in event
    
    # ========== SANITIZATION TESTS ==========
    
    def test_sanitize_string_removes_dangerous_chars(self):
        """Test that sanitize_string removes dangerous characters"""
        dangerous = '<script>alert("XSS")</script>'
        sanitized = sanitize_string(dangerous)
        assert '<script>' not in sanitized
        assert '</script>' not in sanitized
        assert '"' not in sanitized
    
    def test_sanitize_string_preserves_safe_content(self):
        """Test that sanitize_string preserves safe content"""
        safe = 'buy shoes online - best deals 2024'
        sanitized = sanitize_string(safe)
        assert safe == sanitized
    
    def test_sanitize_string_enforces_max_length(self):
        """Test that sanitize_string enforces max length"""
        long_string = 'a' * 500
        sanitized = sanitize_string(long_string)
        assert len(sanitized) <= 200


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])

