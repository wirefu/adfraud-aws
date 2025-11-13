#!/usr/bin/env python3
"""
Local test script for Google Ads tracking endpoint
Tests the Lambda function directly without API Gateway
"""
import json
import sys
import os
import time
from datetime import datetime, timezone

# Set environment variables BEFORE importing boto3
os.environ['AWS_REGION'] = os.environ.get('AWS_REGION', 'us-east-1')
if not os.environ.get('AWS_ACCESS_KEY_ID'):
    os.environ['AWS_ACCESS_KEY_ID'] = 'test-key'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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

def test_google_ads_tracking():
    """Test Google Ads tracking endpoint"""
    print("🛡️  Testing Google Ads Tracking Endpoint")
    print("=" * 50)
    
    # Import the handler
    try:
        from google_ads_tracking.app import lambda_handler
    except ImportError as e:
        print(f"❌ Error importing handler: {e}")
        print("💡 Make sure you're in the project root and have installed dependencies")
        return False
    
    # Set environment variables for testing
    os.environ['DYNAMODB_TABLE_NAME'] = os.environ.get('DYNAMODB_TABLE_NAME', 'fraudguard-events-dev')
    os.environ['ORCHESTRATOR_FUNCTION'] = os.environ.get('ORCHESTRATOR_FUNCTION', 'fraudguard-orchestrator')
    os.environ['FRAUD_THRESHOLD'] = '0.65'
    
    # Load test event
    test_event_path = os.path.join(os.path.dirname(__file__), 'tests', 'events', 'google_ads_event.json')
    
    try:
        with open(test_event_path, 'r') as f:
            event = json.load(f)
    except FileNotFoundError:
        print(f"❌ Test event file not found: {test_event_path}")
        return False
    
    print(f"\n📋 Test Event:")
    print(f"   Method: {event.get('httpMethod')}")
    print(f"   Path: {event.get('path')}")
    print(f"   Query Params: {event.get('queryStringParameters')}")
    
    # Create mock context
    context = MockContext()
    
    # Test the handler
    print(f"\n🚀 Invoking Lambda handler...")
    start_time = time.time()
    
    try:
        response = lambda_handler(event, context)
        elapsed_ms = (time.time() - start_time) * 1000
        
        print(f"\n✅ Handler executed successfully!")
        print(f"   Response time: {elapsed_ms:.2f}ms")
        print(f"   Status code: {response.get('statusCode')}")
        
        # Check response
        if response.get('statusCode') == 204:
            print("   ✅ Correct 204 No Content response")
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
        
        # Print body if present
        if 'body' in response and response['body']:
            body = response.get('body', '')
            if body:
                try:
                    body_json = json.loads(body)
                    print(f"\n📋 Response Body:")
                    print(json.dumps(body_json, indent=2))
                except:
                    print(f"\n📋 Response Body: {body}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error executing handler: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validation():
    """Test parameter validation"""
    print("\n" + "=" * 50)
    print("🧪 Testing Parameter Validation")
    print("=" * 50)
    
    # Set environment variables before importing
    os.environ['DYNAMODB_TABLE_NAME'] = os.environ.get('DYNAMODB_TABLE_NAME', 'fraudguard-events-dev')
    os.environ['ORCHESTRATOR_FUNCTION'] = os.environ.get('ORCHESTRATOR_FUNCTION', 'fraudguard-orchestrator')
    os.environ['FRAUD_THRESHOLD'] = '0.65'
    
    try:
        from google_ads_tracking.app import validate_google_ads_params
    except ImportError as e:
        print(f"❌ Error importing validation function: {e}")
        return False
    
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
    else:
        print(f"   ❌ Validation failed: {errors}")
    
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
    
    return True

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🛡️  Google Ads Tracking - Local Test Suite")
    print("=" * 50)
    
    # Test validation
    test_validation()
    
    # Test full handler
    print("\n" + "=" * 50)
    success = test_google_ads_tracking()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests completed!")
    else:
        print("❌ Some tests failed")
    print("=" * 50)
    print("\n💡 Note: This test runs the Lambda function directly.")
    print("   In production, this would be called via API Gateway at /pt")
    print("   Example: GET https://api.example.com/pt?cid=123&gclid=abc&kw=test")
    print()

