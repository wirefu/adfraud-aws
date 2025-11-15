#!/usr/bin/env python3
"""
Quick script to evaluate existing DynamoDB events through the ML model
No infrastructure setup required - uses existing SageMaker endpoint
"""

import boto3
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.feature_extractor import extract_features
from src.platforms.factory import get_platform_adapter, detect_platform_from_event

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
sagemaker_runtime = boto3.client('sagemaker-runtime', region_name='us-east-1')

# Configuration
TABLE_NAME = 'fraudguard-events-dev'
ENDPOINT_NAME = 'fraudguard-xgboost-endpoint'
BATCH_SIZE = 10  # Process in batches


def get_ml_score(feature_vector: List[float]) -> float:
    """Get ML score from SageMaker endpoint"""
    try:
        # Convert to CSV format
        csv_data = ','.join(map(str, feature_vector))
        
        # Invoke endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType='text/csv',
            Body=csv_data.encode('utf-8')
        )
        
        # Parse response
        result = response['Body'].read().decode('utf-8')
        score = float(result.strip())
        return score
    except Exception as e:
        print(f"Error calling SageMaker: {e}")
        return 0.5  # Fallback score


def get_context_data(event: Dict[str, Any], table_name: str) -> Dict[str, Any]:
    """Get context data for feature extraction"""
    try:
        from src.platforms.factory import get_platform_adapter, detect_platform_from_event
        
        platform_type = detect_platform_from_event(event)
        platform_adapter = get_platform_adapter(platform_type, source=event.get('source'))
        
        # Parse event
        platform_event = platform_adapter.parse_event(event)
        
        # Get context data
        context_data = platform_adapter.get_context_data(platform_event, table_name)
        
        return context_data
    except Exception as e:
        print(f"Warning: Could not get context data: {e}")
        return {}


def evaluate_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a single event through ML model"""
    try:
        # boto3 resource already converts DynamoDB types, but handle both formats
        event_dict = {}
        for key, value in event.items():
            if isinstance(value, dict):
                # DynamoDB client format
                if 'S' in value:
                    event_dict[key] = value['S']
                elif 'N' in value:
                    event_dict[key] = float(value['N']) if '.' in value['N'] else int(value['N'])
                elif 'BOOL' in value:
                    event_dict[key] = value['BOOL']
                elif 'NULL' in value:
                    event_dict[key] = None
                else:
                    event_dict[key] = value
            else:
                # boto3 resource format (already converted)
                if isinstance(value, Decimal):
                    event_dict[key] = float(value)
                else:
                    event_dict[key] = value
        
        # Ensure required fields for feature extraction
        if 'source' not in event_dict and 'platform' not in event_dict:
            event_dict['source'] = 'google_ads' if 'gclid' in event_dict or 'keyword' in event_dict else 'generic'
        if 'platform' not in event_dict:
            event_dict['platform'] = event_dict.get('source', 'generic')
        if 'is_limited_signals' not in event_dict:
            event_dict['is_limited_signals'] = event_dict.get('source') == 'google_ads'
        
        # Get context data
        context_data = get_context_data(event_dict, TABLE_NAME)
        
        # Extract features
        feature_vector = extract_features(event_dict, context_data)
        
        # Model expects 29 features (not 32 with Google Ads features)
        # If we got 32, take only first 29
        if len(feature_vector) > 29:
            feature_vector = feature_vector[:29]
        
        # Get ML score
        ml_score = get_ml_score(feature_vector)
        
        # Determine fraud status and action
        if ml_score > 0.8:
            is_fraud = True
            action = "block"
        elif ml_score < 0.3:
            is_fraud = False
            action = "allow"
        else:
            is_fraud = ml_score > 0.5
            action = "review"
        
        return {
            'ml_score': Decimal(str(ml_score)),
            'is_fraud': is_fraud,
            'action': action,
            'detection_method': 'ml_primary'
        }
    except Exception as e:
        print(f"Error evaluating event: {e}")
        import traceback
        traceback.print_exc()
        return None


def update_event_in_dynamodb(event_id: str, results: Dict[str, Any], output_file=None):
    """Update event in DynamoDB with ML evaluation results, or write to file if update fails"""
    try:
        # Use DynamoDB client directly for more control
        dynamodb_client = boto3.client('dynamodb', region_name='us-east-1')
        
        # Only update ml_score and is_fraud (safe non-key attributes)
        update_expression = "SET ml_score = :ml_score, is_fraud = :is_fraud"
        expression_values = {
            ':ml_score': {'N': str(float(results['ml_score']))},
            ':is_fraud': {'BOOL': results['is_fraud']}
        }
        
        dynamodb_client.update_item(
            TableName=TABLE_NAME,
            Key={'event_id': {'S': event_id}},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        return True
    except Exception as e:
        # If DynamoDB update fails (e.g., GSI key issues), write to file instead
        if output_file:
            result_line = {
                'event_id': event_id,
                'ml_score': float(results['ml_score']),
                'is_fraud': results['is_fraud'],
                'action': results['action'],
                'detection_method': results['detection_method']
            }
            output_file.write(json.dumps(result_line) + '\n')
            output_file.flush()
        return False


def main():
    """Main function to evaluate all events"""
    print("=" * 70)
    print("Evaluating Existing Events Through ML Model")
    print("=" * 70)
    print(f"Table: {TABLE_NAME}")
    print(f"Endpoint: {ENDPOINT_NAME}")
    print()
    
    # Get all events from DynamoDB
    table = dynamodb.Table(TABLE_NAME)
    
    print("Scanning DynamoDB for events...")
    events = []
    last_evaluated_key = None
    
    while True:
        if last_evaluated_key:
            response = table.scan(ExclusiveStartKey=last_evaluated_key)
        else:
            response = table.scan()
        
        events.extend(response.get('Items', []))
        
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break
    
    total_events = len(events)
    print(f"Found {total_events} events to evaluate")
    print()
    
    # Filter out events that already have ML scores
    events_to_evaluate = [
        e for e in events 
        if 'ml_score' not in e or e.get('ml_score') is None
    ]
    
    print(f"Events without ML scores: {len(events_to_evaluate)}")
    print(f"Events already evaluated: {total_events - len(events_to_evaluate)}")
    print()
    
    if not events_to_evaluate:
        print("✅ All events already have ML scores!")
        return
    
    # Process events
    print("Processing events...")
    print()
    
    # Open output file for results that can't be written to DynamoDB
    output_file_path = 'ml_evaluation_results.jsonl'
    output_file = open(output_file_path, 'w')
    print(f"Results file: {output_file_path}")
    print()
    
    evaluated = 0
    errors = 0
    file_writes = 0
    
    for i, event in enumerate(events_to_evaluate, 1):
        # Extract event_id from DynamoDB format
        event_id_raw = event.get('event_id', {})
        if isinstance(event_id_raw, dict):
            event_id = event_id_raw.get('S', 'unknown')
        else:
            event_id = str(event_id_raw) if event_id_raw else 'unknown'
        
        print(f"[{i}/{len(events_to_evaluate)}] Evaluating: {event_id[:50]}...", end=' ')
        
        # Evaluate event
        results = evaluate_event(event)
        
        if results:
            # Update DynamoDB (or write to file if update fails)
            if update_event_in_dynamodb(event_id, results, output_file):
                print(f"✅ Score: {results['ml_score']:.4f}, Fraud: {results['is_fraud']}, Action: {results['action']}")
                evaluated += 1
            else:
                print(f"📝 Score: {results['ml_score']:.4f}, Fraud: {results['is_fraud']} (written to file)")
                file_writes += 1
        else:
            print("❌ Evaluation failed")
            errors += 1
        
        # Progress update every 10 events
        if i % 10 == 0:
            print(f"\nProgress: {i}/{len(events_to_evaluate)} ({i/len(events_to_evaluate)*100:.1f}%)")
            print()
    
    output_file.close()
    
    print()
    print("=" * 70)
    print("Evaluation Complete!")
    print("=" * 70)
    print(f"Total events: {total_events}")
    print(f"Evaluated & updated in DynamoDB: {evaluated}")
    print(f"Evaluated & written to file: {file_writes}")
    print(f"Errors: {errors}")
    print(f"Skipped (already evaluated): {total_events - len(events_to_evaluate)}")
    print()
    if file_writes > 0:
        print(f"📄 Results file: {output_file_path}")
        print(f"   ({file_writes} events written - can be imported later)")
    print()


if __name__ == '__main__':
    main()

