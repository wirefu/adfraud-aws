#!/usr/bin/env python3
"""
Process honeypot clicks through SageMaker endpoint
Queries DynamoDB for honeypot events and evaluates them using the ML model

Usage:
    python scripts/process_honeypot_clicks.py [--table-name TABLE] [--endpoint-name ENDPOINT] [--reprocess-all]

Environment Variables:
    DYNAMODB_TABLE_NAME: DynamoDB table name (default: fraudguard-events-dev)
    SAGEMAKER_ENDPOINT: SageMaker endpoint name (default: fraudguard-xgboost-endpoint)
    AWS_REGION: AWS region (default: us-east-1)
"""

import argparse
import boto3
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.feature_extractor import extract_features

# Import context data function from orchestrator
try:
    from src.orchestrator.app import get_context_data
except ImportError:
    # Fallback: define a simple version if import fails
    def get_context_data(event_id: str, device_id: str, ip_address: str) -> Dict[str, Any]:
        """Simple context data getter (fallback)"""
        return {
            'ip_click_count_24h': 0,
            'device_click_count_1h': 0,
            'time_since_last_click': None,
        }

# Configuration (can be overridden by environment variables or CLI args)
DEFAULT_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'fraudguard-events-dev')
DEFAULT_ENDPOINT_NAME = os.environ.get('SAGEMAKER_ENDPOINT', 'fraudguard-xgboost-endpoint')
DEFAULT_REGION = os.environ.get('AWS_REGION', 'us-east-1')
FRAUD_THRESHOLD = 0.8
LEGITIMATE_THRESHOLD = 0.3

# Global variables (set in main())
TABLE_NAME = DEFAULT_TABLE_NAME
ENDPOINT_NAME = DEFAULT_ENDPOINT_NAME
dynamodb = None
sagemaker_runtime = None


def get_ml_score(feature_vector: List[float], endpoint_name: str = None) -> float:
    """Get ML score from SageMaker endpoint"""
    if endpoint_name is None:
        endpoint_name = ENDPOINT_NAME
    
    try:
        # Convert to CSV format (SageMaker XGBoost expects CSV)
        csv_data = ','.join(map(str, feature_vector))
        
        # Invoke endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='text/csv',
            Body=csv_data.encode('utf-8')
        )
        
        # Parse response (XGBoost returns predictions as CSV)
        result = response['Body'].read().decode('utf-8')
        score = float(result.strip())
        return score
    except Exception as e:
        print(f"Error calling SageMaker endpoint: {e}")
        import traceback
        traceback.print_exc()
        return 0.5  # Fallback score


def convert_dynamodb_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DynamoDB item to Python dict, handling Decimal types"""
    result = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, dict):
            # Handle nested structures
            result[key] = convert_dynamodb_item(value)
        elif isinstance(value, list):
            result[key] = [convert_dynamodb_item(v) if isinstance(v, dict) else v for v in value]
        else:
            result[key] = value
    return result


def evaluate_honeypot_event(event: Dict[str, Any], endpoint_name: str = None) -> Dict[str, Any]:
    """Evaluate a single honeypot event through ML model"""
    try:
        # Convert DynamoDB types to Python types
        event_dict = convert_dynamodb_item(event)
        
        # Ensure required fields for feature extraction
        event_dict['source'] = 'honeypot'
        event_dict['platform'] = 'generic'
        event_dict['is_limited_signals'] = False  # Honeypot has full signals (IP, UA, etc.)
        
        # Get context data (device history, IP history, etc.)
        event_id = event_dict.get('event_id', '')
        device_id = event_dict.get('device_id', '')
        ip_address = event_dict.get('ip_address', '')
        
        context_data = get_context_data(event_id, device_id, ip_address)
        
        # Extract features
        feature_vector = extract_features(event_dict, context_data)
        
        # Model expects 29 features (standard model)
        # If we got more (e.g., 32 with Google Ads features), take only first 29
        if len(feature_vector) > 29:
            feature_vector = feature_vector[:29]
        elif len(feature_vector) < 29:
            # Pad with zeros if we have fewer features
            feature_vector.extend([0.0] * (29 - len(feature_vector)))
        
        # Get ML score from SageMaker
        ml_score = get_ml_score(feature_vector, endpoint_name)
        
        # Decision logic (same as orchestrator)
        if ml_score > FRAUD_THRESHOLD:
            is_fraud = True
            action = "block"
            confidence = 0.8
        elif ml_score < LEGITIMATE_THRESHOLD:
            is_fraud = False
            action = "allow"
            confidence = 0.8
        else:
            is_fraud = ml_score > 0.5
            action = "review"
            confidence = 0.5
        
        return {
            'ml_score': ml_score,
            'is_fraud': is_fraud,
            'action': action,
            'confidence': confidence,
            'detection_method': 'ml_only',
            'fraud_score': ml_score,
        }
    except Exception as e:
        print(f"Error evaluating honeypot event: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_event_with_result(event_id: str, result: Dict[str, Any]) -> bool:
    """Update event in DynamoDB with ML evaluation results"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Build update expression
        update_expression = "SET ml_score = :ml_score, is_fraud = :is_fraud, fraud_score = :fraud_score"
        expression_values = {
            ':ml_score': Decimal(str(result['ml_score'])),
            ':is_fraud': result['is_fraud'],
            ':fraud_score': Decimal(str(result['fraud_score']))
        }
        
        # Add optional fields if they exist
        if 'action' in result:
            update_expression += ", recommended_action = :action"
            expression_values[':action'] = result['action']
        
        if 'confidence' in result:
            update_expression += ", confidence = :confidence"
            expression_values[':confidence'] = Decimal(str(result['confidence']))
        
        if 'detection_method' in result:
            update_expression += ", detection_method = :detection_method"
            expression_values[':detection_method'] = result['detection_method']
        
        # Add updated timestamp
        update_expression += ", updated_at = :updated_at"
        expression_values[':updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # Update item
        table.update_item(
            Key={'event_id': event_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        return True
    except Exception as e:
        print(f"Error updating event {event_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def query_honeypot_events(table_name: str, limit: int = None) -> List[Dict[str, Any]]:
    """Query DynamoDB for honeypot events"""
    try:
        table = dynamodb.Table(table_name)
        
        # Scan for honeypot events
        # Note: This requires a GSI on 'honeypot' field for efficient querying
        # For now, we'll scan and filter
        events = []
        last_evaluated_key = None
        
        print("Scanning DynamoDB for honeypot events...")
        
        while True:
            scan_kwargs = {}
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            if limit:
                scan_kwargs['Limit'] = min(limit - len(events), 100)  # DynamoDB scan limit
            
            response = table.scan(**scan_kwargs)
            
            # Filter for honeypot events
            for item in response.get('Items', []):
                # Check if honeypot field is True
                honeypot_value = item.get('honeypot', False)
                if honeypot_value is True or str(honeypot_value).lower() == 'true':
                    events.append(item)
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            
            # Break if no more items or we've reached the limit
            if not last_evaluated_key or (limit and len(events) >= limit):
                break
        
        return events
    except Exception as e:
        print(f"Error querying honeypot events: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Main function to process honeypot clicks"""
    parser = argparse.ArgumentParser(
        description='Process honeypot clicks through SageMaker endpoint',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--table-name',
        type=str,
        default=DEFAULT_TABLE_NAME,
        help=f'DynamoDB table name (default: {DEFAULT_TABLE_NAME})'
    )
    parser.add_argument(
        '--endpoint-name',
        type=str,
        default=DEFAULT_ENDPOINT_NAME,
        help=f'SageMaker endpoint name (default: {DEFAULT_ENDPOINT_NAME})'
    )
    parser.add_argument(
        '--region',
        type=str,
        default=DEFAULT_REGION,
        help=f'AWS region (default: {DEFAULT_REGION})'
    )
    parser.add_argument(
        '--reprocess-all',
        action='store_true',
        help='Reprocess all events, even those that already have ML scores'
    )
    
    args = parser.parse_args()
    
    # Set global configuration
    global TABLE_NAME, ENDPOINT_NAME, dynamodb, sagemaker_runtime
    
    TABLE_NAME = args.table_name
    ENDPOINT_NAME = args.endpoint_name
    region = args.region
    
    # Initialize AWS clients with specified region
    dynamodb = boto3.resource('dynamodb', region_name=region)
    sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=region)
    
    print("=" * 70)
    print("Processing Honeypot Clicks Through SageMaker Endpoint")
    print("=" * 70)
    print(f"Table: {TABLE_NAME}")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Region: {region}")
    print()
    
    # Query honeypot events
    honeypot_events = query_honeypot_events(TABLE_NAME)
    
    if not honeypot_events:
        print("❌ No honeypot events found in DynamoDB")
        return
    
    print(f"Found {len(honeypot_events)} honeypot events")
    print()
    
    # Filter out events that already have ML scores (unless --reprocess-all is set)
    if args.reprocess_all:
        events_to_process = honeypot_events
        print("⚠️  Reprocessing all events (including those with existing ML scores)")
    else:
        events_to_process = [
            e for e in honeypot_events 
            if 'ml_score' not in e or e.get('ml_score') is None
        ]
    
    if not events_to_process:
        print("✅ All honeypot events already have ML scores!")
        print(f"   Total honeypot events: {len(honeypot_events)}")
        print()
        print("To reprocess all events, use --reprocess-all flag.")
        return
    
    print(f"Events to process: {len(events_to_process)}")
    print(f"Events already processed: {len(honeypot_events) - len(events_to_process)}")
    print()
    
    # Process events
    print("Processing honeypot clicks...")
    print()
    
    processed = 0
    errors = 0
    fraud_detected = 0
    legitimate = 0
    review_needed = 0
    
    for i, event in enumerate(events_to_process, 1):
        event_id = event.get('event_id', 'unknown')
        print(f"[{i}/{len(events_to_process)}] Processing: {event_id[:50]}...", end=' ')
        
        # Evaluate event
        result = evaluate_honeypot_event(event, ENDPOINT_NAME)
        
        if result:
            # Update DynamoDB
            if update_event_with_result(event_id, result):
                ml_score = result['ml_score']
                is_fraud = result['is_fraud']
                action = result['action']
                
                print(f"✅ Score: {ml_score:.4f}, Fraud: {is_fraud}, Action: {action}")
                
                processed += 1
                if is_fraud:
                    fraud_detected += 1
                elif action == 'allow':
                    legitimate += 1
                else:
                    review_needed += 1
            else:
                print("❌ Failed to update DynamoDB")
                errors += 1
        else:
            print("❌ Evaluation failed")
            errors += 1
        
        # Progress update every 10 events
        if i % 10 == 0:
            print(f"\nProgress: {i}/{len(events_to_process)} ({i/len(events_to_process)*100:.1f}%)")
            print()
    
    # Summary
    print()
    print("=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print(f"Total honeypot events: {len(honeypot_events)}")
    print(f"Processed: {processed}")
    print(f"Errors: {errors}")
    print()
    print("Results:")
    print(f"  🚫 Fraud detected: {fraud_detected} ({fraud_detected/processed*100:.1f}%)" if processed > 0 else "  🚫 Fraud detected: 0")
    print(f"  ✅ Legitimate: {legitimate} ({legitimate/processed*100:.1f}%)" if processed > 0 else "  ✅ Legitimate: 0")
    print(f"  ⚠️  Review needed: {review_needed} ({review_needed/processed*100:.1f}%)" if processed > 0 else "  ⚠️  Review needed: 0")
    print()


if __name__ == '__main__':
    main()

