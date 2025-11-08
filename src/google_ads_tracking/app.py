"""
Google Ads Tracking Handler Lambda Function
Handles Google Ads Parallel Tracking requests with <1s response time requirement
"""
import json
import os
import boto3
import re
import threading
from datetime import datetime, timezone
from uuid import uuid4
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

# Initialize AWS clients
lambda_client = boto3.client('lambda')
dynamodb = boto3.resource('dynamodb')

# Environment variables
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
ORCHESTRATOR_FUNCTION = os.environ.get('ORCHESTRATOR_FUNCTION')
FRAUD_THRESHOLD = float(os.environ.get('FRAUD_THRESHOLD', '0.65'))

# Input validation schema
VALIDATION_SCHEMA = {
    'gclid': {
        'type': str,
        'max_length': 100,
        'pattern': r'^[a-zA-Z0-9_-]+$',
        'required': False
    },
    'cid': {
        'type': str,
        'max_length': 50,
        'pattern': r'^[a-zA-Z0-9_-]+$',
        'required': True
    },
    'kw': {
        'type': str,
        'max_length': 200,
        'required': False,
        'sanitize': True
    },
    'aid': {
        'type': str,
        'max_length': 50,
        'pattern': r'^[a-zA-Z0-9_-]+$',
        'required': False
    },
    'target': {
        'type': str,
        'max_length': 200,
        'required': False
    },
    'mt': {
        'type': str,
        'max_length': 20,
        'required': False
    },
    'device': {
        'type': str,
        'max_length': 20,
        'required': False
    },
    'creative': {
        'type': str,
        'max_length': 50,
        'required': False
    }
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle Google Ads parallel tracking request
    
    CRITICAL: Must respond with 204 No Content in <1 second
    
    Args:
        event: API Gateway event containing query parameters
        context: Lambda context object
        
    Returns:
        API Gateway response with 204 status code
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        # Extract query parameters from API Gateway event
        query_params = event.get('queryStringParameters') or {}
        
        # Validate and sanitize parameters
        validated_params, validation_errors = validate_google_ads_params(query_params)
        
        if validation_errors:
            return create_error_response(400, f"Validation errors: {', '.join(validation_errors)}")
        
        # RESPOND IMMEDIATELY with 204 No Content (required by Google)
        # This must happen before any processing
        response = {
            'statusCode': 204,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'text/plain'
            },
            'body': ''
        }
        
        # Calculate response time (must be < 1 second)
        response_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        # Log if response time is approaching limit
        if response_time_ms > 800:
            print(f"WARNING: Response time {response_time_ms}ms approaching 1s limit")
        
        # Process fraud detection asynchronously AFTER responding
        # Use threading to avoid blocking (Lambda will keep container warm)
        thread = threading.Thread(
            target=process_fraud_detection_async,
            args=(validated_params, start_time),
            daemon=True
        )
        thread.start()
        
        return response
        
    except Exception as e:
        # Even on error, return 204 to avoid Google timeout
        # Log error for monitoring
        print(f"Error in Google Ads tracking handler: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 204,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'text/plain'
            },
            'body': ''
        }


def validate_google_ads_params(query_params: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[list]]:
    """
    Validate and sanitize Google Ads query parameters
    
    Args:
        query_params: Query parameters from API Gateway
        
    Returns:
        Tuple of (validated_params, errors)
    """
    errors = []
    validated = {}
    
    for param, schema in VALIDATION_SCHEMA.items():
        value = query_params.get(param)
        
        if schema.get('required') and not value:
            errors.append(f"Missing required parameter: {param}")
            continue
        
        if value:
            # Type checking
            if not isinstance(value, schema['type']):
                errors.append(f"Invalid type for {param}: expected {schema['type'].__name__}")
                continue
            
            # Length checking
            if 'max_length' in schema and len(value) > schema['max_length']:
                errors.append(f"Parameter {param} exceeds max length: {schema['max_length']}")
                continue
            
            # Pattern matching
            if 'pattern' in schema:
                if not re.match(schema['pattern'], value):
                    errors.append(f"Parameter {param} does not match required pattern")
                    continue
            
            # Sanitize for XSS
            if schema.get('sanitize'):
                value = sanitize_string(value)
            
            validated[param] = value
    
    if errors:
        return None, errors
    
    return validated, None


def sanitize_string(value: str) -> str:
    """
    Sanitize string to prevent XSS attacks
    
    Args:
        value: String to sanitize
        
    Returns:
        Sanitized string
    """
    # Remove potentially dangerous characters
    # Keep alphanumeric, spaces, and common punctuation
    sanitized = re.sub(r'[<>"\']', '', value)
    return sanitized[:200]  # Enforce max length


def process_fraud_detection_async(params: Dict[str, Any], request_time: datetime) -> None:
    """
    Process fraud detection asynchronously after responding to Google
    
    Args:
        params: Validated Google Ads parameters
        request_time: Original request timestamp
    """
    try:
        # Map Google Ads parameters to event structure
        event_data = map_google_ads_to_event(params, request_time)
        
        # Store raw event in DynamoDB (for Google refund compatibility)
        store_google_ads_event(event_data)
        
        # Trigger fraud orchestrator asynchronously
        trigger_fraud_orchestrator(event_data)
        
    except Exception as e:
        # Log error but don't fail (already responded to Google)
        print(f"Error in async fraud detection processing: {str(e)}")
        import traceback
        traceback.print_exc()


def map_google_ads_to_event(params: Dict[str, Any], request_time: datetime) -> Dict[str, Any]:
    """
    Map Google Ads query parameters to FraudGuard event structure
    
    Args:
        params: Validated Google Ads parameters
        request_time: Request timestamp
        
    Returns:
        Event dictionary compatible with FraudGuard system
    """
    event_id = str(uuid4())
    timestamp = int(request_time.timestamp())
    
    # Map Google Ads parameters to event structure
    event = {
        'event_id': event_id,
        'timestamp': timestamp,
        'source': 'google_ads',
        'event_type': 'click',
        
        # Google Ads identifiers (REQUIRED for refunds)
        'gclid': params.get('gclid', ''),  # CRITICAL for refunds
        'campaign_id': params.get('cid', ''),  # Required
        'ad_group_id': params.get('aid', ''),  # REQUIRED for refunds
        'keyword': params.get('kw', ''),  # REQUIRED for refunds
        'target_id': params.get('target', ''),  # REQUIRED for refunds
        
        # Optional Google Ads parameters
        'match_type': params.get('mt', ''),
        'device': params.get('device', ''),
        'creative_id': params.get('creative', ''),
        
        # Not available in parallel tracking (Phase 1)
        'ip_address': None,  # Not available in parallel tracking
        'device_id': None,  # Not available in parallel tracking
        'user_agent': None,  # Not available in parallel tracking
        'referrer': None,  # Not available in parallel tracking
        
        # Metadata
        'created_at': request_time.isoformat(),
        'ttl': timestamp + (7 * 24 * 60 * 60),  # 7 days TTL
    }
    
    return event


def store_google_ads_event(event: Dict[str, Any]) -> None:
    """
    Store Google Ads event in DynamoDB
    
    Args:
        event: Event dictionary
    """
    if not TABLE_NAME:
        print("WARNING: DYNAMODB_TABLE_NAME not set, skipping storage")
        return
    
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Convert floats to Decimal for DynamoDB compatibility
        event = convert_floats_to_decimal(event)
        
        table.put_item(Item=event)
        
    except Exception as e:
        print(f"Error storing Google Ads event: {str(e)}")
        # Don't raise - already responded to Google


def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Convert float values to Decimal for DynamoDB compatibility
    
    Args:
        obj: Object to convert
        
    Returns:
        Object with floats converted to Decimal
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj


def trigger_fraud_orchestrator(event: Dict[str, Any]) -> None:
    """
    Trigger fraud orchestrator Lambda function asynchronously
    
    Args:
        event: Event dictionary
    """
    if not ORCHESTRATOR_FUNCTION:
        print("WARNING: ORCHESTRATOR_FUNCTION not set, skipping fraud detection")
        return
    
    try:
        lambda_client.invoke(
            FunctionName=ORCHESTRATOR_FUNCTION,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(event)
        )
    except Exception as e:
        print(f"Error triggering orchestrator: {str(e)}")
        # Don't raise - already responded to Google


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create standardized error response
    
    Args:
        status_code: HTTP status code
        message: Error message
        
    Returns:
        API Gateway error response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message,
            'status': 'error'
        })
    }

