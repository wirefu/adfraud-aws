#!/usr/bin/env python3
"""
Analyze fraud-flagged ads and display detailed information
"""

import json
import boto3
from collections import defaultdict
from decimal import Decimal

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
TABLE_NAME = 'fraudguard-events-dev'

def convert_dynamodb_value(value):
    """Convert DynamoDB value to Python type"""
    if isinstance(value, dict):
        if 'S' in value:
            return value['S']
        elif 'N' in value:
            return float(value['N']) if '.' in value['N'] else int(value['N'])
        elif 'BOOL' in value:
            return value['BOOL']
        elif 'NULL' in value:
            return None
    elif isinstance(value, Decimal):
        return float(value)
    return value

def get_event_details(event_id):
    """Get full event details from DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'event_id': event_id})
        
        if 'Item' in response:
            item = response['Item']
            # Convert DynamoDB types
            event = {}
            for key, value in item.items():
                event[key] = convert_dynamodb_value(value)
            return event
        return None
    except Exception as e:
        print(f"Error getting event {event_id}: {e}")
        return None

def main():
    """Main function to analyze fraud-flagged ads"""
    print("=" * 80)
    print("Fraud-Flagged Ads Analysis")
    print("=" * 80)
    print()
    
    # Read evaluation results
    try:
        with open('ml_evaluation_results.jsonl', 'r') as f:
            results = [json.loads(line) for line in f]
    except FileNotFoundError:
        print("❌ ml_evaluation_results.jsonl not found. Run evaluate_existing_events.py first.")
        return
    
    # Filter fraud-flagged events
    fraud_events = [r for r in results if r.get('is_fraud')]
    
    print(f"📊 Summary:")
    print(f"   Total Evaluated: {len(results)}")
    print(f"   Fraud-Flagged: {len(fraud_events)} ({len(fraud_events)/len(results)*100:.1f}%)")
    print(f"   Not Fraud: {len(results) - len(fraud_events)}")
    print()
    
    if not fraud_events:
        print("✅ No fraud-flagged ads found!")
        return
    
    # Get ML score statistics
    scores = [e['ml_score'] for e in fraud_events]
    print(f"📈 ML Score Statistics (Fraud-Flagged):")
    print(f"   Min: {min(scores):.4f}")
    print(f"   Max: {max(scores):.4f}")
    print(f"   Avg: {sum(scores)/len(scores):.4f}")
    print()
    
    # Get detailed information for fraud-flagged ads
    print("🔍 Fetching detailed information for fraud-flagged ads...")
    print()
    
    fraud_details = []
    campaigns = defaultdict(lambda: {'count': 0, 'total_cost': 0, 'scores': []})
    
    for i, result in enumerate(fraud_events[:50], 1):  # Limit to first 50 for display
        event_id = result['event_id']
        event_details = get_event_details(event_id)
        
        if event_details:
            fraud_details.append({
                'event_id': event_id,
                'ml_score': result['ml_score'],
                'action': result.get('action', 'N/A'),
                'campaign_id': event_details.get('campaign_id', 'N/A'),
                'keyword': event_details.get('keyword', 'N/A'),
                'target_id': event_details.get('target_id', 'N/A'),
                'gclid': event_details.get('gclid', 'N/A'),
                'cost_micros': event_details.get('cost_micros', 0),
                'cost_usd': float(event_details.get('cost_micros', 0)) / 1000000 if event_details.get('cost_micros') else 0,
                'ctr': event_details.get('ctr', 0),
                'clicks': event_details.get('clicks', 0),
                'impressions': event_details.get('impressions', 0),
                'timestamp': event_details.get('timestamp', 'N/A'),
                'date': event_details.get('shifted_date', 'N/A'),
            })
            
            # Aggregate by campaign
            campaign_id = event_details.get('campaign_id', 'unknown')
            campaigns[campaign_id]['count'] += 1
            campaigns[campaign_id]['total_cost'] += float(event_details.get('cost_micros', 0)) / 1000000
            campaigns[campaign_id]['scores'].append(result['ml_score'])
        
        if i % 10 == 0:
            print(f"   Processed {i}/{min(50, len(fraud_events))} events...")
    
    print()
    print("=" * 80)
    print("Fraud-Flagged Ads Details")
    print("=" * 80)
    print()
    
    # Display individual fraud-flagged ads
    print(f"📋 Sample Fraud-Flagged Ads (showing first {min(20, len(fraud_details))}):")
    print()
    
    for i, ad in enumerate(fraud_details[:20], 1):
        print(f"{i}. Event ID: {ad['event_id'][:60]}...")
        print(f"   Campaign ID: {ad['campaign_id']}")
        print(f"   Keyword: {str(ad['keyword'])[:50]}")
        print(f"   Target ID: {ad['target_id']}")
        print(f"   GCLID: {str(ad['gclid'])[:40]}")
        print(f"   ML Score: {ad['ml_score']:.4f}")
        print(f"   Action: {ad['action']}")
        print(f"   Cost: ${ad['cost_usd']:.2f}")
        print(f"   CTR: {ad['ctr']}")
        print(f"   Clicks: {ad['clicks']}")
        print(f"   Date: {ad['date']}")
        print()
    
    # Campaign-level summary
    print("=" * 80)
    print("Campaign-Level Fraud Summary")
    print("=" * 80)
    print()
    
    print(f"{'Campaign ID':<20} {'Fraud Events':<15} {'Total Cost':<15} {'Avg ML Score':<15}")
    print("-" * 80)
    
    for campaign_id, stats in sorted(campaigns.items(), key=lambda x: x[1]['count'], reverse=True)[:20]:
        avg_score = sum(stats['scores']) / len(stats['scores'])
        print(f"{str(campaign_id):<20} {stats['count']:<15} ${stats['total_cost']:<14.2f} {avg_score:<15.4f}")
    
    print()
    
    # Total cost of fraud
    total_fraud_cost = sum(ad['cost_usd'] for ad in fraud_details)
    print(f"💰 Total Cost of Fraud-Flagged Ads: ${total_fraud_cost:.2f}")
    print(f"📊 Average Cost per Fraud Event: ${total_fraud_cost/len(fraud_details):.2f}")
    print()

if __name__ == '__main__':
    main()

