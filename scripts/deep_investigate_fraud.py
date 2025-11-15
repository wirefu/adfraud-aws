#!/usr/bin/env python3
"""
Deep investigation of fraud-flagged campaigns and events
Analyzes patterns, feature distributions, and suspicious behaviors
"""

import json
import boto3
from collections import defaultdict, Counter
from datetime import datetime
import statistics

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
            event = {}
            for key, value in item.items():
                event[key] = convert_dynamodb_value(value)
            return event
        return None
    except Exception as e:
        print(f"Error getting event {event_id}: {e}")
        return None

def analyze_campaign_patterns(fraud_events, all_events):
    """Analyze patterns within specific campaigns"""
    print("\n" + "=" * 80)
    print("CAMPAIGN-LEVEL DEEP DIVE")
    print("=" * 80)
    
    # Group by campaign
    campaign_data = defaultdict(lambda: {
        'events': [],
        'keywords': [],
        'costs': [],
        'ctrs': [],
        'dates': [],
        'gclids': []
    })
    
    for result in fraud_events:
        event_id = result['event_id']
        event_details = get_event_details(event_id)
        
        if event_details:
            campaign_id = event_details.get('campaign_id', 'unknown')
            campaign_data[campaign_id]['events'].append({
                'event_id': event_id,
                'ml_score': result['ml_score'],
                'details': event_details
            })
            campaign_data[campaign_id]['keywords'].append(event_details.get('keyword', ''))
            campaign_data[campaign_id]['costs'].append(float(event_details.get('cost_micros', 0)) / 1000000)
            campaign_data[campaign_id]['ctrs'].append(event_details.get('ctr', 0))
            campaign_data[campaign_id]['dates'].append(event_details.get('shifted_date', ''))
            campaign_data[campaign_id]['gclids'].append(event_details.get('gclid', ''))
    
    # Analyze top campaigns
    top_campaigns = sorted(campaign_data.items(), key=lambda x: len(x[1]['events']), reverse=True)[:5]
    
    for campaign_id, data in top_campaigns:
        print(f"\n📊 Campaign {campaign_id}")
        print("-" * 80)
        print(f"   Total Fraud Events: {len(data['events'])}")
        print(f"   Total Cost: ${sum(data['costs']):.2f}")
        print(f"   Average Cost: ${statistics.mean(data['costs']):.2f}")
        print(f"   Cost Range: ${min(data['costs']):.2f} - ${max(data['costs']):.2f}")
        print(f"   Average CTR: {statistics.mean(data['ctrs']):.4f} ({statistics.mean(data['ctrs'])*100:.2f}%)")
        print(f"   CTR Range: {min(data['ctrs']):.4f} - {max(data['ctrs']):.4f}")
        
        # Keyword analysis
        keyword_counts = Counter([k for k in data['keywords'] if k])
        print(f"\n   Top Keywords:")
        for keyword, count in keyword_counts.most_common(5):
            print(f"      - '{keyword}': {count} events")
        
        # Date range
        dates = [d for d in data['dates'] if d]
        if dates:
            print(f"\n   Date Range: {min(dates)} to {max(dates)}")
            print(f"   Events Span: {len(set(dates))} unique days")
        
        # GCLID pattern analysis
        gclids = [g for g in data['gclids'] if g]
        if gclids:
            api_gclids = [g for g in gclids if g.startswith('API-')]
            print(f"\n   GCLID Analysis:")
            print(f"      Total GCLIDs: {len(gclids)}")
            print(f"      API-Generated: {len(api_gclids)} ({len(api_gclids)/len(gclids)*100:.1f}%)")
            print(f"      User-Generated: {len(gclids) - len(api_gclids)}")
        
        # Time pattern analysis
        if len(data['events']) > 1:
            print(f"\n   Event Frequency:")
            print(f"      Average events per day: {len(data['events']) / max(1, len(set(dates))):.2f}")
            
            # Check for burst patterns
            date_counts = Counter(data['dates'])
            max_events_per_day = max(date_counts.values()) if date_counts else 0
            print(f"      Max events in single day: {max_events_per_day}")
            
            if max_events_per_day > 5:
                print(f"      ⚠️  WARNING: High event concentration detected!")

def analyze_keyword_patterns(fraud_events):
    """Analyze patterns by keyword"""
    print("\n" + "=" * 80)
    print("KEYWORD-LEVEL ANALYSIS")
    print("=" * 80)
    
    keyword_data = defaultdict(lambda: {
        'count': 0,
        'total_cost': 0,
        'avg_ctr': [],
        'campaigns': set(),
        'ml_scores': []
    })
    
    for result in fraud_events:
        event_id = result['event_id']
        event_details = get_event_details(event_id)
        
        if event_details:
            keyword = event_details.get('keyword', '')
            if keyword:
                keyword_data[keyword]['count'] += 1
                keyword_data[keyword]['total_cost'] += float(event_details.get('cost_micros', 0)) / 1000000
                keyword_data[keyword]['avg_ctr'].append(event_details.get('ctr', 0))
                keyword_data[keyword]['campaigns'].add(event_details.get('campaign_id', ''))
                keyword_data[keyword]['ml_scores'].append(result['ml_score'])
    
    # Sort by count
    top_keywords = sorted(keyword_data.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
    
    print(f"\n{'Keyword':<40} {'Events':<10} {'Total Cost':<15} {'Avg CTR':<15} {'Campaigns':<10}")
    print("-" * 90)
    
    for keyword, data in top_keywords:
        avg_ctr = statistics.mean(data['avg_ctr']) if data['avg_ctr'] else 0
        print(f"{keyword[:40]:<40} {data['count']:<10} ${data['total_cost']:<14.2f} {avg_ctr*100:<14.2f}% {len(data['campaigns']):<10}")
    
    # Identify suspicious keywords
    print("\n⚠️  Suspicious Keywords (High CTR or High Cost):")
    for keyword, data in top_keywords:
        avg_ctr = statistics.mean(data['avg_ctr']) if data['avg_ctr'] else 0
        if avg_ctr > 0.10 or data['total_cost'] > 50:
            print(f"   - '{keyword}': {data['count']} events, ${data['total_cost']:.2f} cost, {avg_ctr*100:.2f}% CTR")

def analyze_temporal_patterns(fraud_events):
    """Analyze time-based patterns"""
    print("\n" + "=" * 80)
    print("TEMPORAL PATTERN ANALYSIS")
    print("=" * 80)
    
    dates = []
    hours = []
    
    for result in fraud_events[:100]:  # Sample for performance
        event_id = result['event_id']
        event_details = get_event_details(event_id)
        
        if event_details:
            date_str = event_details.get('shifted_date', '')
            timestamp = event_details.get('timestamp', 0)
            
            if date_str:
                dates.append(date_str)
            
            if timestamp:
                try:
                    dt = datetime.fromtimestamp(timestamp)
                    hours.append(dt.hour)
                except:
                    pass
    
    if dates:
        date_counts = Counter(dates)
        print(f"\n📅 Date Distribution (Top 10 Days):")
        for date, count in date_counts.most_common(10):
            print(f"   {date}: {count} fraud events")
    
    if hours:
        hour_counts = Counter(hours)
        print(f"\n🕐 Hour Distribution (Top 5 Hours):")
        for hour, count in hour_counts.most_common(5):
            print(f"   {hour:02d}:00: {count} fraud events")

def analyze_feature_patterns(fraud_events):
    """Analyze Google Ads performance features"""
    print("\n" + "=" * 80)
    print("GOOGLE ADS FEATURE ANALYSIS")
    print("=" * 80)
    
    features = {
        'keyword_fraud_rate': [],
        'target_fraud_rate': [],
        'gclid_pattern_score': [],
        'ctr': [],
        'cost_per_click': []
    }
    
    for result in fraud_events[:100]:  # Sample for performance
        event_id = result['event_id']
        event_details = get_event_details(event_id)
        
        if event_details:
            if 'keyword_fraud_rate' in event_details:
                features['keyword_fraud_rate'].append(event_details['keyword_fraud_rate'])
            if 'target_fraud_rate' in event_details:
                features['target_fraud_rate'].append(event_details['target_fraud_rate'])
            if 'gclid_pattern_score' in event_details:
                features['gclid_pattern_score'].append(event_details['gclid_pattern_score'])
            if 'ctr' in event_details:
                features['ctr'].append(event_details['ctr'])
            
            # Calculate cost per click
            cost = float(event_details.get('cost_micros', 0)) / 1000000
            clicks = event_details.get('clicks', 0)
            if clicks > 0:
                features['cost_per_click'].append(cost / clicks)
    
    print("\n📊 Feature Statistics:")
    for feature_name, values in features.items():
        if values:
            print(f"\n   {feature_name.replace('_', ' ').title()}:")
            print(f"      Count: {len(values)}")
            print(f"      Min: {min(values):.4f}")
            print(f"      Max: {max(values):.4f}")
            print(f"      Avg: {statistics.mean(values):.4f}")
            print(f"      Median: {statistics.median(values):.4f}")

def main():
    """Main investigation function"""
    print("=" * 80)
    print("DEEP FRAUD INVESTIGATION REPORT")
    print("=" * 80)
    
    # Read evaluation results
    try:
        with open('ml_evaluation_results.jsonl', 'r') as f:
            results = [json.loads(line) for line in f]
    except FileNotFoundError:
        print("❌ ml_evaluation_results.jsonl not found.")
        return
    
    fraud_events = [r for r in results if r.get('is_fraud')]
    
    print(f"\n📊 Overview:")
    print(f"   Total Fraud Events: {len(fraud_events)}")
    print(f"   ML Score Range: {min([e['ml_score'] for e in fraud_events]):.4f} - {max([e['ml_score'] for e in fraud_events]):.4f}")
    print(f"   Average ML Score: {statistics.mean([e['ml_score'] for e in fraud_events]):.4f}")
    
    # Run analyses
    analyze_campaign_patterns(fraud_events, results)
    analyze_keyword_patterns(fraud_events)
    analyze_temporal_patterns(fraud_events)
    analyze_feature_patterns(fraud_events)
    
    print("\n" + "=" * 80)
    print("INVESTIGATION COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    from decimal import Decimal
    main()

