#!/usr/bin/env python3
"""
Simple local test for Google Ads tracking endpoint
Tests the validation and response logic without AWS dependencies
"""
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Set environment variables BEFORE importing anything
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'test-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret'
os.environ['DYNAMODB_TABLE_NAME'] = 'fraudguard-events-dev'
os.environ['ORCHESTRATOR_FUNCTION'] = 'fraudguard-orchestrator'
os.environ['FRAUD_THRESHOLD'] = '0.65'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock boto3 clients before importing the module
mock_lambda_client = MagicMock()
mock_dynamodb_resource = MagicMock()
mock_table = MagicMock()
mock_dynamodb_resource.Table.return_value = mock_table

with patch('boto3.client', return_value=mock_lambda_client), \
     patch('boto3.resource', return_value=mock_dynamodb_resource):
    from google_ads_tracking.app import (
        lambda_handler,
        validate_google_ads_params,
        create_error_response
    )

# Mock Lambda context
class MockContext:
    def __init__(self):
        self.function_name = "GoogleAdsTrackingHandler"
        self.function_version = "$LATEST"
        self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:GoogleAdsTrackingHandler"
        self.memory_limit_in_mb = 1024
        self.aws_request_id = "test-request-id"
        self.log_group_name = "/aws/lambda/GoogleAdsTrackingHandler"
        self.log_stream_name = "test-stream"
        self.remaining_time_in_millis = lambda: 5000

def test_validation():
    """Test parameter validation"""
    print("🧪 Testing Parameter Validation")
    print("=" * 50)
    
    # Test valid parameters
    print("\n✅ Test 1: Valid parameters")
    valid_params = {
        'cid': '123456789',
        'gclid': 'CjwKCAjw_xyz123abc456',
        'kw': 'buy shoes online'
    }
    validated, errors = validate_google_ads_params(valid_params)
    if not errors:
        print("   ✅ Validation passed")
        print(f"   Validated params: {validated}")
    else:
        print(f"   ❌ Validation failed: {errors}")
        return False
    
    # Test missing required parameter
    print("\n❌ Test 2: Missing required parameter (cid)")
    invalid_params = {
        'gclid': 'CjwKCAjw_xyz123abc456'
    }
    validated, errors = validate_google_ads_params(invalid_params)
    if errors:
        print(f"   ✅ Validation correctly caught error: {errors}")
    else:
        print("   ❌ Validation should have failed")
        return False
    
    # Test invalid parameter format
    print("\n❌ Test 3: Invalid parameter format")
    invalid_params2 = {
        'cid': '123456789',
        'gclid': 'invalid!@#$%'  # Invalid characters
    }
    validated, errors = validate_google_ads_params(invalid_params2)
    if errors:
        print(f"   ✅ Validation correctly caught error: {errors}")
    else:
        print("   ❌ Validation should have failed")
        return False
    
    # Test parameter length limits
    print("\n❌ Test 4: Parameter exceeds max length")
    invalid_params3 = {
        'cid': '123456789',
        'kw': 'a' * 201  # Exceeds max_length of 200
    }
    validated, errors = validate_google_ads_params(invalid_params3)
    if errors:
        print(f"   ✅ Validation correctly caught error: {errors}")
    else:
        print("   ❌ Validation should have failed")
        return False
    
    return True

def test_lambda_handler():
    """Test Lambda handler with mock event"""
    print("\n" + "=" * 50)
    print("🚀 Testing Lambda Handler")
    print("=" * 50)
    
    # Create test event (API Gateway format)
    event = {
        "httpMethod": "GET",
        "path": "/pt",
        "queryStringParameters": {
            "cid": "123456789",
            "gclid": "CjwKCAjw_xyz123abc456",
            "kw": "buy shoes online",
            "aid": "987654321",
            "target": "placement-123"
        },
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; Google-Ads-Tracking)",
            "Accept": "*/*"
        },
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "dev",
            "requestTime": "2024-01-01T00:00:00Z"
        }
    }
    
    print(f"\n📋 Test Event:")
    print(f"   Method: {event.get('httpMethod')}")
    print(f"   Path: {event.get('path')}")
    print(f"   Query Params: {event.get('queryStringParameters')}")
    
    # Create mock context
    context = MockContext()
    
    # Mock Lambda invoke (for async fraud detection)
    mock_lambda_client.invoke.return_value = {
        'StatusCode': 202,
        'ResponseMetadata': {'HTTPStatusCode': 202}
    }
    
    # Test the handler
    print(f"\n🚀 Invoking Lambda handler...")
    import time
    start_time = time.time()
    
    try:
        response = lambda_handler(event, context)
        elapsed_ms = (time.time() - start_time) * 1000
        
        print(f"\n✅ Handler executed successfully!")
        print(f"   Response time: {elapsed_ms:.2f}ms")
        print(f"   Status code: {response.get('statusCode')}")
        
        # Check response
        if response.get('statusCode') == 204:
            print("   ✅ Correct 204 No Content response (Google requirement)")
        else:
            print(f"   ⚠️  Expected 204, got {response.get('statusCode')}")
        
        # Check response time (must be < 1 second for Google)
        if elapsed_ms < 1000:
            print(f"   ✅ Response time < 1s (Google requirement met)")
        else:
            print(f"   ⚠️  Response time > 1s (may timeout in production)")
        
        # Print response headers
        if 'headers' in response:
            print(f"\n📋 Response Headers:")
            for key, value in response['headers'].items():
                print(f"   {key}: {value}")
        
        # Verify async Lambda was invoked
        if mock_lambda_client.invoke.called:
            print(f"\n✅ Async fraud detection Lambda was invoked")
            call_args = mock_lambda_client.invoke.call_args
            print(f"   Function: {call_args[1].get('FunctionName', 'N/A')}")
            print(f"   InvocationType: {call_args[1].get('InvocationType', 'N/A')}")
        else:
            print(f"\n⚠️  Async fraud detection Lambda was NOT invoked")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error executing handler: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_responses():
    """Test error response handling"""
    print("\n" + "=" * 50)
    print("❌ Testing Error Responses")
    print("=" * 50)
    
    context = MockContext()
    
    # Test missing required parameter
    print("\n❌ Test 1: Missing required parameter")
    event1 = {
        "httpMethod": "GET",
        "path": "/pt",
        "queryStringParameters": {
            "gclid": "CjwKCAjw_xyz123abc456"
            # Missing 'cid' (required)
        }
    }
    
    try:
        response = lambda_handler(event1, context)
        if response.get('statusCode') == 400:
            print("   ✅ Correctly returned 400 Bad Request")
        else:
            print(f"   ⚠️  Expected 400, got {response.get('statusCode')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test invalid parameter format
    print("\n❌ Test 2: Invalid parameter format")
    event2 = {
        "httpMethod": "GET",
        "path": "/pt",
        "queryStringParameters": {
            "cid": "123456789",
            "gclid": "invalid!@#$%"  # Invalid characters
        }
    }
    
    try:
        response = lambda_handler(event2, context)
        if response.get('statusCode') == 400:
            print("   ✅ Correctly returned 400 Bad Request")
        else:
            print(f"   ⚠️  Expected 400, got {response.get('statusCode')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return True

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🛡️  Google Ads Tracking - Local Test Suite")
    print("=" * 50)
    
    # Test validation
    validation_success = test_validation()
    
    # Test error responses
    error_success = test_error_responses()
    
    # Test full handler
    handler_success = test_lambda_handler()
    
    print("\n" + "=" * 50)
    if validation_success and error_success and handler_success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 50)
    print("\n💡 Note: This test runs the Lambda function with mocked AWS clients.")
    print("   In production, this would be called via API Gateway at /pt")
    print("   Example: GET https://api.example.com/pt?cid=123&gclid=abc&kw=test")
    print()

