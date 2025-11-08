"""
Edge case and stress tests for Google Ads tracking endpoint
Tests production failure scenarios and DoS resistance
"""
import json
import sys
import os
import time
from unittest.mock import Mock, patch, MagicMock

# Set environment variables BEFORE importing anything
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'test-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret'
os.environ['DYNAMODB_TABLE_NAME'] = 'fraudguard-events-dev'
os.environ['ORCHESTRATOR_FUNCTION'] = 'fraudguard-orchestrator'
os.environ['FRAUD_THRESHOLD'] = '0.65'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock boto3 clients
mock_lambda_client = MagicMock()
mock_dynamodb_resource = MagicMock()
mock_table = MagicMock()
mock_dynamodb_resource.Table.return_value = mock_table

with patch('boto3.client', return_value=mock_lambda_client), \
     patch('boto3.resource', return_value=mock_dynamodb_resource):
    from google_ads_tracking.app import lambda_handler, validate_google_ads_params


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


def test_concurrent_requests():
    """Test handling of concurrent requests (threading safety)"""
    print("\n🔄 Testing Concurrent Requests")
    print("=" * 50)
    
    import threading
    
    results = []
    errors = []
    
    def make_request(i):
        try:
            event = {
                'httpMethod': 'GET',
                'path': '/pt',
                'queryStringParameters': {
                    'cid': f'campaign-{i}',
                    'gclid': f'gclid-{i}',
                    'kw': f'keyword-{i}'
                }
            }
            context = MockContext()
            response = lambda_handler(event, context)
            results.append(response['statusCode'])
        except Exception as e:
            errors.append(str(e))
    
    # Create 10 concurrent requests
    threads = []
    for i in range(10):
        thread = threading.Thread(target=make_request, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads
    for thread in threads:
        thread.join()
    
    print(f"   ✅ Processed {len(results)} concurrent requests")
    print(f"   ✅ All returned 204: {all(r == 204 for r in results)}")
    print(f"   ❌ Errors: {len(errors)}")
    
    assert len(results) == 10
    assert all(r == 204 for r in results)
    assert len(errors) == 0


def test_malformed_event_structure():
    """Test handling of malformed event structures"""
    print("\n🔧 Testing Malformed Event Structures")
    print("=" * 50)
    
    context = MockContext()
    
    # Test cases
    test_cases = [
        ("Missing httpMethod", {}),
        ("Missing path", {'httpMethod': 'GET'}),
        ("Invalid httpMethod", {'httpMethod': 'POST', 'path': '/pt'}),
        ("Nested query params", {'httpMethod': 'GET', 'path': '/pt', 'queryStringParameters': {'nested': {'key': 'value'}}}),
        ("List in query params", {'httpMethod': 'GET', 'path': '/pt', 'queryStringParameters': {'cid': ['123', '456']}}),
    ]
    
    for name, event in test_cases:
        print(f"\n   Testing: {name}")
        try:
            response = lambda_handler(event, context)
            # Validation errors return 400, exceptions return 204
            assert response['statusCode'] in [204, 400], f"Unexpected status: {response['statusCode']}"
            print(f"      ✅ Handled gracefully: {response['statusCode']}")
        except Exception as e:
            print(f"      ❌ Exception: {e}")
            # Even exceptions should be caught and return 204
            assert False, f"Exception not caught: {e}"


def test_parameter_injection_attempts():
    """Test various injection attack attempts"""
    print("\n🔒 Testing Injection Attack Attempts")
    print("=" * 50)
    
    context = MockContext()
    
    injection_attempts = [
        ("SQL Injection", {'cid': "123'; DROP TABLE events; --", 'gclid': 'abc'}),
        ("NoSQL Injection", {'cid': '123', 'gclid': {'$ne': None}}),
        ("Command Injection", {'cid': '123; rm -rf /', 'gclid': 'abc'}),
        ("LDAP Injection", {'cid': '123)(&', 'gclid': 'abc'}),
        ("XPath Injection", {'cid': "123' or '1'='1", 'gclid': 'abc'}),
    ]
    
    for name, params in injection_attempts:
        print(f"\n   Testing: {name}")
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': params
        }
        try:
            response = lambda_handler(event, context)
            # Should either validate and sanitize, or return 400
            assert response['statusCode'] in [204, 400]
            print(f"      ✅ Handled: {response['statusCode']}")
        except Exception as e:
            print(f"      ❌ Exception: {e}")
            assert False, f"Exception not caught: {e}"


def test_unicode_edge_cases():
    """Test Unicode edge cases"""
    print("\n🌐 Testing Unicode Edge Cases")
    print("=" * 50)
    
    context = MockContext()
    
    unicode_cases = [
        ("Emoji", {'cid': '123', 'kw': 'buy shoes 😀🎉'}),
        ("Zero-width characters", {'cid': '123', 'kw': 'buy\u200bshoes'}),
        ("Right-to-left text", {'cid': '123', 'kw': 'זה טקסט בעברית'}),
        ("Mixed scripts", {'cid': '123', 'kw': 'buy 鞋子 シューズ'}),
        ("Control characters", {'cid': '123', 'kw': 'buy\x00shoes'}),
    ]
    
    for name, params in unicode_cases:
        print(f"\n   Testing: {name}")
        event = {
            'httpMethod': 'GET',
            'path': '/pt',
            'queryStringParameters': params
        }
        try:
            response = lambda_handler(event, context)
            assert response['statusCode'] in [204, 400]
            print(f"      ✅ Handled: {response['statusCode']}")
        except Exception as e:
            print(f"      ❌ Exception: {e}")
            assert False, f"Exception not caught: {e}"


def test_response_time_under_load():
    """Test response time under simulated load"""
    print("\n⏱️  Testing Response Time Under Load")
    print("=" * 50)
    
    context = MockContext()
    times = []
    
    event = {
        'httpMethod': 'GET',
        'path': '/pt',
        'queryStringParameters': {
            'cid': '123456789',
            'gclid': 'CjwKCAjw_xyz123abc456',
            'kw': 'buy shoes online'
        }
    }
    
    # Run 100 requests
    for i in range(100):
        start = time.time()
        response = lambda_handler(event, context)
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
        assert response['statusCode'] == 204
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    p95_time = sorted(times)[int(len(times) * 0.95)]
    
    print(f"   ✅ Average response time: {avg_time:.2f}ms")
    print(f"   ✅ Max response time: {max_time:.2f}ms")
    print(f"   ✅ P95 response time: {p95_time:.2f}ms")
    print(f"   ✅ All < 1s: {all(t < 1000 for t in times)}")
    
    assert all(t < 1000 for t in times), f"Some responses exceeded 1s: max={max_time}ms"
    assert avg_time < 100, f"Average response time too high: {avg_time}ms"


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🛡️  Google Ads Tracking - Edge Case Test Suite")
    print("=" * 50)
    
    try:
        test_concurrent_requests()
        test_malformed_event_structure()
        test_parameter_injection_attempts()
        test_unicode_edge_cases()
        test_response_time_under_load()
        
        print("\n" + "=" * 50)
        print("✅ All edge case tests passed!")
        print("=" * 50)
    except Exception as e:
        print("\n" + "=" * 50)
        print(f"❌ Test failed: {e}")
        print("=" * 50)
        import traceback
        traceback.print_exc()
        sys.exit(1)

