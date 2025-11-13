"""
Fraud Analytics Dashboard
Streamlit-based web dashboard for monitoring real-time fraud metrics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import boto3
from typing import Dict, Any, List, Optional
import json
import os
import sys
import io
import csv

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.storage.dynamodb_utils import (
    query_events_by_gclid,
    query_events_by_keyword,
    query_events_by_target,
    query_events_by_campaign
)

# Google Ads API integration (optional)
try:
    from google_ads_api_integration import (
        get_google_ads_api_client,
        fetch_google_ads_campaigns,
        fetch_google_ads_performance,
        fetch_google_ads_keywords,
        fetch_google_ads_placements,
        fetch_google_ads_optimization_scores,
        fetch_google_ads_quality_scores,
        fetch_google_ads_recommendations,
        merge_google_ads_with_fraud_data,
        GOOGLE_ADS_API_AVAILABLE
    )
except ImportError:
    GOOGLE_ADS_API_AVAILABLE = False
    get_google_ads_api_client = None
    fetch_google_ads_campaigns = None
    fetch_google_ads_performance = None
    fetch_google_ads_keywords = None
    fetch_google_ads_placements = None
    fetch_google_ads_optimization_scores = None
    fetch_google_ads_quality_scores = None
    fetch_google_ads_recommendations = None
    merge_google_ads_with_fraud_data = None

# Page configuration
st.set_page_config(
    page_title="FraudGuard AI Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize AWS clients
@st.cache_resource
def get_dynamodb_client():
    """Get DynamoDB client"""
    return boto3.resource('dynamodb', region_name='us-east-1')

@st.cache_resource
def get_s3_client():
    """Get S3 client"""
    return boto3.client('s3', region_name='us-east-1')

# Configuration
# Default table name matches SAM template output
# Can be overridden via environment variable DYNAMODB_TABLE_NAME
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'fraudguard-events-dev')
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', '')

# Initialize clients
dynamodb = get_dynamodb_client()
s3 = get_s3_client()
table = dynamodb.Table(TABLE_NAME) if TABLE_NAME else None


def get_recent_events(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Get recent events from DynamoDB
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        List of event dictionaries
    """
    if not table:
        # Return mock data for development
        return get_mock_events(hours)
    
    try:
        # Verify table exists by checking its status
        table.load()
    except Exception as e:
        # Table doesn't exist or can't be accessed
        st.warning(f"⚠️ DynamoDB table '{TABLE_NAME}' not found. Using mock data for demonstration.")
        st.info(f"💡 To use real data, ensure the table exists in AWS. Error: {str(e)}")
        return get_mock_events(hours)
    
    try:
        # Calculate timestamp threshold
        threshold = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        
        # Scan table for recent events
        # Note: 'timestamp' is a reserved keyword in DynamoDB, so we use ExpressionAttributeNames
        response = table.scan(
            FilterExpression='#ts >= :threshold',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={':threshold': threshold}
        )
        
        items = response.get('Items', [])
        
        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='#ts >= :threshold',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={':threshold': threshold},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))
        
        if not items:
            st.info(f"ℹ️ No events found in the last {hours} hours. Using mock data for demonstration.")
            return get_mock_events(hours)
        
        return items
    except Exception as e:
        st.error(f"Error fetching events: {str(e)}")
        st.info("Using mock data for demonstration.")
        return get_mock_events(hours)


def get_google_ads_events(
    hours: int = 24,
    campaign_id: Optional[str] = None,
    target_id: Optional[str] = None,
    keyword: Optional[str] = None,
    gclid: Optional[str] = None,
    fraud_threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Get Google Ads events from DynamoDB with filtering
    
    Args:
        hours: Number of hours to look back
        campaign_id: Campaign ID filter ("All" or specific ID)
        target_id: Target ID filter ("All" or specific ID)
        keyword: Keyword filter ("All" or specific keyword)
        gclid: GCLID search string
        fraud_threshold: Minimum fraud score (0.0-1.0)
        
    Returns:
        List of Google Ads event dictionaries
    """
    if not table:
        # Return mock Google Ads events for development
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        return _filter_google_ads_events(google_ads_events, campaign_id, target_id, keyword, gclid, fraud_threshold)
    
    try:
        table.load()
    except Exception as e:
        st.warning(f"⚠️ DynamoDB table '{TABLE_NAME}' not found. Using mock data for demonstration.")
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        return _filter_google_ads_events(google_ads_events, campaign_id, target_id, keyword, gclid, fraud_threshold)
    
    try:
        # Calculate timestamp range
        now = datetime.now(timezone.utc)
        start_timestamp = int((now - timedelta(hours=hours)).timestamp())
        end_timestamp = int(now.timestamp())
        
        events = []
        
        # Query logic (priority order)
        if gclid and gclid.strip():
            # Priority 1: GCLID lookup
            events = query_events_by_gclid(TABLE_NAME, gclid.strip(), start_timestamp, end_timestamp)
        elif keyword and keyword != "All" and keyword.strip():
            # Priority 2: Keyword filter
            events = query_events_by_keyword(TABLE_NAME, keyword.strip(), start_timestamp, end_timestamp)
        elif target_id and target_id != "All" and target_id.strip():
            # Priority 3: Target filter
            events = query_events_by_target(TABLE_NAME, target_id.strip(), start_timestamp, end_timestamp)
        elif campaign_id and campaign_id != "All" and campaign_id.strip():
            # Priority 4: Campaign filter
            events = query_events_by_campaign(TABLE_NAME, campaign_id.strip(), start_timestamp, end_timestamp)
        else:
            # Priority 5: Scan table with source filter - include both google_ads and google_ads_api
            response = table.scan(
                FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start AND #ts <= :end',
                ExpressionAttributeNames={
                    '#src': 'source',
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':source1': 'google_ads',
                    ':source2': 'google_ads_api',
                    ':start': start_timestamp,
                    ':end': end_timestamp
                }
            )
            events = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = table.scan(
                    FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start AND #ts <= :end',
                    ExpressionAttributeNames={
                        '#src': 'source',
                        '#ts': 'timestamp'
                    },
                    ExpressionAttributeValues={
                        ':source1': 'google_ads',
                        ':source2': 'google_ads_api',
                        ':start': start_timestamp,
                        ':end': end_timestamp
                    },
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                events.extend(response.get('Items', []))
        
        # Post-query filtering
        filtered_events = []
        for event in events:
            # Filter by source - include both 'google_ads' and 'google_ads_api' sources
            source = event.get('source', '')
            if source not in ['google_ads', 'google_ads_api']:
                continue
            
            # Filter by fraud threshold
            fraud_score = float(event.get('fraud_score', 0.0))
            if fraud_score < fraud_threshold:
                continue
            
            # Apply additional filters if not already applied via GSI
            if not gclid and not (keyword and keyword != "All") and not (target_id and target_id != "All"):
                if campaign_id and campaign_id != "All":
                    if event.get('campaign_id') != campaign_id:
                        continue
            
            filtered_events.append(event)
        
        if not filtered_events:
            st.info(f"ℹ️ No Google Ads events found matching the filters. Using mock data for demonstration.")
            all_events = get_mock_events(hours)
            google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
            return _filter_google_ads_events(google_ads_events, campaign_id, target_id, keyword, gclid, fraud_threshold)
        
        return filtered_events
    except Exception as e:
        st.error(f"Error fetching Google Ads events: {str(e)}")
        st.info("Using mock data for demonstration.")
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        return _filter_google_ads_events(google_ads_events, campaign_id, target_id, keyword, gclid, fraud_threshold)


def _filter_google_ads_events(
    events: List[Dict[str, Any]],
    campaign_id: Optional[str],
    target_id: Optional[str],
    keyword: Optional[str],
    gclid: Optional[str],
    fraud_threshold: float
) -> List[Dict[str, Any]]:
    """Filter Google Ads events in memory (for mock data)"""
    filtered = []
    for event in events:
        if event.get('source') != 'google_ads':
            continue
        
        if gclid and gclid.strip():
            if event.get('gclid', '').strip() != gclid.strip():
                continue
        
        if campaign_id and campaign_id != "All":
            if event.get('campaign_id') != campaign_id:
                continue
        
        if target_id and target_id != "All":
            if event.get('target_id') != target_id:
                continue
        
        if keyword and keyword != "All":
            if event.get('keyword', '').strip() != keyword.strip():
                continue
        
        fraud_score = float(event.get('fraud_score', 0.0))
        if fraud_score < fraud_threshold:
            continue
        
        filtered.append(event)
    
    return filtered


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_unique_google_ads_campaigns(table_name: str, hours: int) -> List[str]:
    """Get unique campaign IDs from Google Ads events"""
    if not table:
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        campaigns = sorted(set([e.get('campaign_id', '') for e in google_ads_events if e.get('campaign_id')]))
        return [c for c in campaigns if c]
    
    try:
        table.load()
        now = datetime.now(timezone.utc)
        start_timestamp = int((now - timedelta(hours=hours)).timestamp())
        
        response = table.scan(
            FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start',
            ExpressionAttributeNames={
                '#src': 'source',
                '#ts': 'timestamp'
            },
            ExpressionAttributeValues={
                ':source1': 'google_ads',
                ':source2': 'google_ads_api',
                ':start': start_timestamp
            },
            ProjectionExpression='campaign_id'
        )
        
        campaigns = set()
        for item in response.get('Items', []):
            if item.get('campaign_id'):
                campaigns.add(item['campaign_id'])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start',
                ExpressionAttributeNames={
                    '#src': 'source',
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':source1': 'google_ads',
                    ':source2': 'google_ads_api',
                    ':start': start_timestamp
                },
                ProjectionExpression='campaign_id',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            for item in response.get('Items', []):
                if item.get('campaign_id'):
                    campaigns.add(item['campaign_id'])
        
        return sorted(list(campaigns))
    except Exception:
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        campaigns = sorted(set([e.get('campaign_id', '') for e in google_ads_events if e.get('campaign_id')]))
        return [c for c in campaigns if c]


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_unique_google_ads_targets(table_name: str, hours: int) -> List[str]:
    """Get unique target IDs from Google Ads events"""
    if not table:
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        targets = sorted(set([e.get('target_id', '') for e in google_ads_events if e.get('target_id')]))
        return [t for t in targets if t]
    
    try:
        table.load()
        now = datetime.now(timezone.utc)
        start_timestamp = int((now - timedelta(hours=hours)).timestamp())
        
        response = table.scan(
            FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start',
            ExpressionAttributeNames={
                '#src': 'source',
                '#ts': 'timestamp'
            },
            ExpressionAttributeValues={
                ':source1': 'google_ads',
                ':source2': 'google_ads_api',
                ':start': start_timestamp
            },
            ProjectionExpression='target_id'
        )
        
        targets = set()
        for item in response.get('Items', []):
            if item.get('target_id'):
                targets.add(item['target_id'])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start',
                ExpressionAttributeNames={
                    '#src': 'source',
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':source1': 'google_ads',
                    ':source2': 'google_ads_api',
                    ':start': start_timestamp
                },
                ProjectionExpression='target_id',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            for item in response.get('Items', []):
                if item.get('target_id'):
                    targets.add(item['target_id'])
        
        return sorted(list(targets))
    except Exception:
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        targets = sorted(set([e.get('target_id', '') for e in google_ads_events if e.get('target_id')]))
        return [t for t in targets if t]


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_unique_google_ads_keywords(table_name: str, hours: int) -> List[str]:
    """Get unique keywords from Google Ads events"""
    if not table:
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        keywords = sorted(set([e.get('keyword', '') for e in google_ads_events if e.get('keyword')]))
        return [k for k in keywords if k]
    
    try:
        table.load()
        now = datetime.now(timezone.utc)
        start_timestamp = int((now - timedelta(hours=hours)).timestamp())
        
        response = table.scan(
            FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start',
            ExpressionAttributeNames={
                '#src': 'source',
                '#ts': 'timestamp'
            },
            ExpressionAttributeValues={
                ':source1': 'google_ads',
                ':source2': 'google_ads_api',
                ':start': start_timestamp
            },
            ProjectionExpression='keyword'
        )
        
        keywords = set()
        for item in response.get('Items', []):
            if item.get('keyword'):
                keywords.add(item['keyword'])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='(#src = :source1 OR #src = :source2) AND #ts >= :start',
                ExpressionAttributeNames={
                    '#src': 'source',
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':source1': 'google_ads',
                    ':source2': 'google_ads_api',
                    ':start': start_timestamp
                },
                ProjectionExpression='keyword',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            for item in response.get('Items', []):
                if item.get('keyword'):
                    keywords.add(item['keyword'])
        
        return sorted(list(keywords))
    except Exception:
        all_events = get_mock_events(hours)
        google_ads_events = [e for e in all_events if e.get('source') == 'google_ads']
        keywords = sorted(set([e.get('keyword', '') for e in google_ads_events if e.get('keyword')]))
        return [k for k in keywords if k]


def generate_mock_reasoning(is_fraud: bool, campaign_id: str, ip_address: str, fraud_type: str = 'unknown') -> str:
    """Generate detailed mock AI reasoning"""
    if not is_fraud:
        return f"This event shows legitimate traffic patterns from IP {ip_address} in campaign {campaign_id}. Normal user behavior detected with consistent click patterns, valid user agent, and expected geographic location. No suspicious activity identified."

    fraud_types = {
        'bot_traffic': f"This event exhibits clear bot traffic patterns. The IP address {ip_address} shows automated behavior with non-human click patterns. The user agent string indicates a bot framework, and the click velocity exceeds normal human interaction rates. Campaign {campaign_id} has been flagged for review due to high bot activity.",
        'click_farm': f"Click farm activity detected from IP {ip_address} in campaign {campaign_id}. Multiple rapid clicks from the same source with identical patterns suggest coordinated fraudulent activity. The geographic location and timing patterns are consistent with known click farm operations. Immediate action recommended.",
        'device_farm': f"Device farm indicators present. IP {ip_address} shows multiple device IDs with identical behavioral patterns, suggesting device spoofing. Campaign {campaign_id} is experiencing coordinated fraud attempts. The device fingerprinting reveals anomalies consistent with farm operations.",
        'click_injection': f"Click injection fraud detected from IP {ip_address} in campaign {campaign_id}. A malicious app on the device monitored for new app installations and injected a fake click just before the install completed (<1 second timing). This pattern indicates install broadcast monitoring, where the fraudster steals attribution credit for legitimate app installs. The click-to-install time of less than 1 second is highly suspicious and characteristic of click injection attacks. Immediate blocking recommended.",
        'incentivized_clicks': f"Incentivized click fraud detected from IP {ip_address} in campaign {campaign_id}. This event shows a pattern of high click volume with extremely low or zero conversion rate, indicating users are clicking ads for rewards rather than genuine interest. The engagement score is very low, suggesting users are not actually engaging with the content after clicking. This is characteristic of incentivized traffic where users are paid or rewarded to click ads. Immediate review recommended.",
        'competitor_clicking': f"Competitor clicking fraud detected from IP {ip_address} in campaign {campaign_id}. The IP address matches known competitor ranges or business/office networks, and shows a pattern of high click volume with zero conversions. This suggests a competitor is clicking ads to drain the ad budget without generating any legitimate value. The timing patterns and geographic location further support this conclusion. Immediate blocking recommended.",
        'proxy_fraud': f"Proxy/fake click fraud detected from IP {ip_address} in campaign {campaign_id}. The IP address is from a proxy server (beyond VPN), and shows low engagement scores with no conversions. This pattern indicates fake clicks generated through proxy servers to mask the real source. The combination of proxy IP, low engagement, and zero conversions is highly suspicious. Immediate blocking recommended."
    }

    return fraud_types.get(fraud_type, f"Fraudulent activity detected from IP {ip_address} in campaign {campaign_id}. Multiple suspicious indicators suggest this is not legitimate traffic.")


def get_mock_events(hours: int = 24) -> List[Dict[str, Any]]:
    """Generate mock events for development"""
    import random
    try:
        from faker import Faker
        fake = Faker()
    except ImportError:
        # Fallback if faker not available
        fake = None
    events = []
    now = datetime.now(timezone.utc)
    
    fraud_types = ['bot_traffic', 'click_farm', 'device_farm', 'click_injection', 'incentivized_clicks', 'competitor_clicking', 'proxy_fraud']
    
    # Scale event count based on time period for more realistic historical data
    # Base: 100 events per 24 hours, scale proportionally
    base_count = 100
    scale_factor = max(1, hours / 24)  # At least 1x for short periods
    total_count = int(base_count * scale_factor)
    
    # Generate some Google Ads events (30% of total)
    google_ads_count = int(total_count * 0.3)
    regular_count = total_count - google_ads_count
    
    # Generate Google Ads events
    for i in range(google_ads_count):
        is_fraud = random.random() < 0.3  # 30% fraud rate
        campaign_id = f'campaign-{random.randint(1, 10)}'
        primary_fraud_type = random.choice(fraud_types) if is_fraud else 'legitimate'
        
        # Generate GCLID (Google Click ID format)
        gclid = f'Cj0KCQi{"".join([random.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz") for _ in range(20)])}'
        
        event = {
            'event_id': f'google-ads-event-{i}',
            'timestamp': int((now - timedelta(minutes=random.randint(0, hours*60))).timestamp()),
            'source': 'google_ads',
            'event_type': 'click',
            'is_fraud': is_fraud,
            'fraud_score': random.uniform(0.7, 0.95) if is_fraud else random.uniform(0.1, 0.4),
            'campaign_id': campaign_id,
            'gclid': gclid,
            'keyword': random.choice(['buy shoes', 'nike air', 'running shoes', 'sneakers', 'athletic wear', '']),
            'target_id': f'placement-{random.randint(1, 5)}',
            'ad_group_id': f'adgroup-{random.randint(1, 20)}',
            'primary_fraud_type': primary_fraud_type,
            'fraud_signals': random.sample(['suspicious_keyword', 'high_fraud_rate', 'suspicious_timing'], k=random.randint(1, 3)) if is_fraud else [],
            'reasoning': generate_mock_reasoning(is_fraud, campaign_id, 'N/A (Google Ads)', primary_fraud_type)
        }
        events.append(event)
    
    # Generate regular events
    for i in range(regular_count):
        is_fraud = random.random() < 0.3  # 30% fraud rate
        campaign_id = f'campaign-{random.randint(1, 10)}'
        ip_address = fake.ipv4() if fake else f'192.168.{random.randint(1, 255)}.{random.randint(1, 255)}'
        primary_fraud_type = random.choice(fraud_types) if is_fraud else 'legitimate'
        
        # Generate fraud-specific data
        click_to_install_time = None
        conversion_rate = None
        engagement_score = None
        ip_is_proxy = False
        ip_is_business = False
        ip_is_competitor = False
        
        if primary_fraud_type == 'click_injection':
            # Click injection: <1 second is highly suspicious
            click_to_install_time = random.uniform(0.1, 0.9)  # <1 second
        elif primary_fraud_type == 'incentivized_clicks':
            # Incentivized clicks: very low conversion rate, low engagement
            conversion_rate = random.uniform(0.0, 0.001)  # <0.1% conversion rate
            engagement_score = random.uniform(0.0, 0.3)  # Low engagement
        elif primary_fraud_type == 'competitor_clicking':
            # Competitor clicking: zero conversions, business IP
            conversion_rate = 0.0  # Zero conversions
            ip_is_business = True
            ip_is_competitor = random.random() < 0.5  # 50% chance of known competitor IP
        elif primary_fraud_type == 'proxy_fraud':
            # Proxy fraud: proxy IP, low engagement, no conversions
            ip_is_proxy = True
            engagement_score = random.uniform(0.0, 0.3)  # Low engagement
            conversion_rate = 0.0  # No conversions
        elif is_fraud and random.random() < 0.2:  # 20% chance of having install data for other fraud types
            click_to_install_time = random.uniform(30, 300)  # Normal range
        
        event = {
            'event_id': f'event-{i}',
            'timestamp': int((now - timedelta(minutes=random.randint(0, hours*60))).timestamp()),
            'source': 'regular',
            'is_fraud': is_fraud,
            'fraud_score': random.uniform(0.7, 0.95) if is_fraud else random.uniform(0.1, 0.4),
            'campaign_id': campaign_id,
            'publisher_id': f'publisher-{random.randint(1, 5)}',
            'ip_address': ip_address,
            'ip_country': fake.country_code() if fake else random.choice(['US', 'GB', 'CA', 'DE', 'FR']),
            'primary_fraud_type': primary_fraud_type,
            'fraud_signals': random.sample(['bot_user_agent', 'high_click_velocity', 'datacenter_ip', 'suspicious_timing'], k=random.randint(1, 3)) if is_fraud else [],
            'reasoning': generate_mock_reasoning(is_fraud, campaign_id, ip_address, primary_fraud_type)
        }
        
        # Add fraud-specific fields
        if click_to_install_time is not None:
            event['click_to_install_time_sec'] = click_to_install_time
            event['has_recent_install'] = True
            event['install_broadcast_detected'] = click_to_install_time < 1.0
            event['click_injection_risk_score'] = 0.95 if click_to_install_time < 1.0 else 0.3
            event['is_mobile'] = True  # Click injection is mobile-only
        
        if conversion_rate is not None:
            event['conversion_rate'] = conversion_rate
            event['clicks_count'] = random.randint(10, 100) if primary_fraud_type == 'incentivized_clicks' else random.randint(1, 10)
            event['conversions_count'] = int(event['clicks_count'] * conversion_rate)
        
        if engagement_score is not None:
            event['engagement_score'] = engagement_score
        
        if ip_is_proxy:
            event['ip_is_proxy'] = True
        
        if ip_is_business:
            event['ip_is_business'] = True
        
        if ip_is_competitor:
            event['ip_is_competitor'] = True
        
        events.append(event)
    
    return events


def calculate_metrics(events: List[Dict[str, Any]], cost_per_click: float = 0.50) -> Dict[str, Any]:
    """Calculate dashboard metrics from events"""
    if not events:
        return {
            'total_events': 0,
            'fraud_count': 0,
            'fraud_rate': 0.0,
            'legitimate_count': 0,
            'total_ad_spend': 0.0,
            'fraud_loss': 0.0,
            'fraud_by_type': {},
            'top_signals': {},
            'fraud_by_campaign': {},
            'fraud_by_country': {},
            'cost_by_country': {},
            'fraud_cost_by_country': {}
        }
    
    df = pd.DataFrame(events)
    
    # Parse honeypot field (convert to boolean)
    if 'honeypot' in df.columns:
        df['honeypot'] = df['honeypot'].apply(lambda x: True if x is True or x == True or str(x).lower() == 'true' else False)
    
    # Basic metrics
    total_events = len(df)
    fraud_count = df['is_fraud'].sum() if 'is_fraud' in df.columns else 0
    fraud_rate = (fraud_count / total_events * 100) if total_events > 0 else 0.0
    
    # Cost calculations
    total_ad_spend = total_events * cost_per_click
    fraud_loss = fraud_count * cost_per_click
    
    # Fraud by type
    fraud_by_type = {}
    if 'primary_fraud_type' in df.columns:
        fraud_df = df[df['is_fraud'] == True] if 'is_fraud' in df.columns else df
        fraud_by_type = fraud_df['primary_fraud_type'].value_counts().to_dict()
    
    # Top fraud signals
    top_signals = {}
    if 'fraud_signals' in df.columns:
        all_signals = []
        for signals in df['fraud_signals'].dropna():
            if isinstance(signals, list):
                all_signals.extend(signals)
        if all_signals:
            top_signals = pd.Series(all_signals).value_counts().head(10).to_dict()
    
    # Fraud by campaign
    fraud_by_campaign = {}
    if 'campaign_id' in df.columns and 'is_fraud' in df.columns:
        campaign_fraud = df.groupby('campaign_id').agg({
            'is_fraud': ['sum', 'count']
        }).reset_index()
        campaign_fraud.columns = ['campaign_id', 'fraud_count', 'total_count']
        campaign_fraud['fraud_rate'] = (campaign_fraud['fraud_count'] / campaign_fraud['total_count'] * 100).round(2)
        fraud_by_campaign = campaign_fraud.set_index('campaign_id')['fraud_rate'].to_dict()
    
    # Fraud by country
    fraud_by_country = {}
    if 'ip_country' in df.columns and 'is_fraud' in df.columns:
        country_fraud = df.groupby('ip_country').agg({
            'is_fraud': ['sum', 'count']
        }).reset_index()
        country_fraud.columns = ['country', 'fraud_count', 'total_count']
        country_fraud['fraud_rate'] = (country_fraud['fraud_count'] / country_fraud['total_count'] * 100).round(2)
        fraud_by_country = country_fraud.set_index('country')['fraud_rate'].to_dict()
    
    # Cost by country
    cost_by_country = {}
    if 'ip_country' in df.columns:
        country_cost = df.groupby('ip_country').size().reset_index(name='count')
        country_cost['cost'] = country_cost['count'] * cost_per_click
        cost_by_country = country_cost.set_index('ip_country')['cost'].to_dict()
    
    # Fraud cost by country
    fraud_cost_by_country = {}
    if 'ip_country' in df.columns and 'is_fraud' in df.columns:
        fraud_df = df[df['is_fraud'] == True] if 'is_fraud' in df.columns else pd.DataFrame()
        if not fraud_df.empty and 'ip_country' in fraud_df.columns:
            country_fraud_cost = fraud_df.groupby('ip_country').size().reset_index(name='fraud_count')
            country_fraud_cost['fraud_cost'] = country_fraud_cost['fraud_count'] * cost_per_click
            fraud_cost_by_country = country_fraud_cost.set_index('ip_country')['fraud_cost'].to_dict()
    
    return {
        'total_events': total_events,
        'fraud_count': int(fraud_count),
        'fraud_rate': round(fraud_rate, 2),
        'legitimate_count': int(total_events - fraud_count),
        'total_ad_spend': round(total_ad_spend, 2),
        'fraud_loss': round(fraud_loss, 2),
        'fraud_by_type': fraud_by_type,
        'top_signals': top_signals,
        'fraud_by_campaign': fraud_by_campaign,
        'fraud_by_country': fraud_by_country,
        'cost_by_country': cost_by_country,
        'fraud_cost_by_country': fraud_cost_by_country
    }


def render_real_time_overview(events: List[Dict[str, Any]], metrics: Dict[str, Any], cost_per_click: float = 0.50):
    """Render real-time overview dashboard"""
    st.header("📊 Real-Time Overview")
    
    # Filter honeypot events
    honeypot_events = [e for e in events if e.get('honeypot') == True]
    regular_events = [e for e in events if not e.get('honeypot')]
    
    # Show honeypot stats if available
    if honeypot_events:
        honeypot_metrics = calculate_metrics(honeypot_events, cost_per_click)
        with st.expander("🍯 Honeypot Events", expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Honeypot Events", len(honeypot_events))
            with col2:
                st.metric("Honeypot Fraud", honeypot_metrics['fraud_count'], delta=f"{honeypot_metrics['fraud_rate']:.1f}%")
            with col3:
                st.metric("Honeypot Legitimate", honeypot_metrics['legitimate_count'])
            with col4:
                st.metric("Honeypot Fraud Rate", f"{honeypot_metrics['fraud_rate']:.2f}%")
    
    # Key metrics - Updated to match screenshot
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Events (24h)", metrics['total_events'])
    
    with col2:
        st.metric("Fraud Detected", metrics['fraud_count'], delta=f"{metrics['fraud_rate']:.1f}%")
    
    with col3:
        st.metric("Total Ad Spend", f"${metrics['total_ad_spend']:.2f}")
    
    with col4:
        st.metric("Fraud Loss", f"${metrics['fraud_loss']:.2f}")
    
    st.divider()
    
    # Charts row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Fraud by Type")
        if metrics['fraud_by_type']:
            fig = px.pie(
                values=list(metrics['fraud_by_type'].values()),
                names=list(metrics['fraud_by_type'].keys()),
                title="Fraud Type Distribution"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No fraud data available")
    
    with col2:
        st.subheader("Top Fraud Signals")
        if metrics['top_signals']:
            signals_df = pd.DataFrame({
                'Signal': list(metrics['top_signals'].keys()),
                'Count': list(metrics['top_signals'].values())
            })
            fig = px.bar(
                signals_df,
                x='Count',
                y='Signal',
                orientation='h',
                title="Most Common Fraud Signals"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No fraud signals available")
    
    # Geographic heatmap - Updated to show fraud cost
    st.subheader("🌍 Geographic Fraud Distribution")
    if metrics['fraud_cost_by_country']:
        country_df = pd.DataFrame({
            'Country': list(metrics['fraud_cost_by_country'].keys()),
            'Fraud Cost ($)': list(metrics['fraud_cost_by_country'].values())
        })
        
        # Create choropleth map showing fraud cost
        fig = px.choropleth(
            country_df,
            locations='Country',
            locationmode='ISO-3',
            color='Fraud Cost ($)',
            title="Fraud Cost by Country",
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No geographic data available")
    
    # Cost by Country Table
    st.subheader("Cost by Country")
    if metrics['cost_by_country']:
        cost_df = pd.DataFrame({
            'Country': list(metrics['cost_by_country'].keys()),
            'Cost': list(metrics['cost_by_country'].values())
        }).sort_values('Cost', ascending=False)
        st.dataframe(cost_df, use_container_width=True, hide_index=True)
    else:
        st.info("No cost data available")
    
    # Fraud Cost by Country Bar Chart
    st.subheader("Fraud Cost by Country")
    if metrics['fraud_cost_by_country']:
        fraud_cost_df = pd.DataFrame({
            'Country': list(metrics['fraud_cost_by_country'].keys()),
            'Fraud Cost ($)': list(metrics['fraud_cost_by_country'].values())
        }).sort_values('Fraud Cost ($)', ascending=False)
        
        fig = px.bar(
            fraud_cost_df,
            x='Country',
            y='Fraud Cost ($)',
            title="Fraud Cost by Country",
            color='Fraud Cost ($)',
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No fraud cost data available")
    
    # Honeypot events breakdown
    if honeypot_events:
        st.divider()
        st.subheader("🍯 Honeypot Events Breakdown")
        honeypot_df = pd.DataFrame(honeypot_events)
        
        col1, col2 = st.columns(2)
        with col1:
            if 'button_id' in honeypot_df.columns:
                button_counts = honeypot_df['button_id'].value_counts()
                if not button_counts.empty:
                    st.write("**Clicks by Button:**")
                    for button, count in button_counts.items():
                        st.write(f"  • {button}: {count}")
        
        with col2:
            if 'view_time_ms' in honeypot_df.columns:
                avg_view_time = honeypot_df['view_time_ms'].mean()
                st.metric("Average View Time", f"{avg_view_time:.0f} ms")
        
        # Show honeypot event types
        if 'event_type' in honeypot_df.columns:
            event_type_counts = honeypot_df['event_type'].value_counts()
            if not event_type_counts.empty:
                st.write("**Event Types:**")
                for event_type, count in event_type_counts.items():
                    st.write(f"  • {event_type}: {count}")


def render_campaign_analysis(events: List[Dict[str, Any]], metrics: Dict[str, Any]):
    """Render campaign analysis view"""
    st.header("📈 Campaign Analysis")
    
    if not metrics['fraud_by_campaign']:
        st.info("No campaign data available")
        return
    
    # Campaign fraud rates
    campaign_df = pd.DataFrame({
        'Campaign': list(metrics['fraud_by_campaign'].keys()),
        'Fraud Rate (%)': list(metrics['fraud_by_campaign'].values())
    }).sort_values('Fraud Rate (%)', ascending=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Fraud Rate by Campaign")
        fig = px.bar(
            campaign_df,
            x='Campaign',
            y='Fraud Rate (%)',
            title="Campaign Fraud Rates"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Campaign Summary")
        st.dataframe(campaign_df, use_container_width=True)
    
    # Time series for selected campaign
    st.subheader("📊 Click Pattern Analysis")
    if events:
        events_df = pd.DataFrame(events)
        if 'campaign_id' in events_df.columns and 'timestamp' in events_df.columns:
            # Convert timestamp to datetime
            events_df['datetime'] = pd.to_datetime(events_df['timestamp'], unit='s')
            events_df['hour'] = events_df['datetime'].dt.hour
            
            # Hourly click pattern
            hourly_clicks = events_df.groupby('hour').size().reset_index(name='clicks')
            fig = px.line(
                hourly_clicks,
                x='hour',
                y='clicks',
                title="Hourly Click Pattern (Last 24h)",
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)


def render_event_detail(events: List[Dict[str, Any]]):
    """Render event detail view"""
    st.header("🔍 Event Detail View")
    
    if not events:
        st.info("No events available")
        return
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        show_honeypot = st.checkbox("Show Honeypot Events", value=True)
    with col2:
        show_regular = st.checkbox("Show Regular Events", value=True)
    
    # Filter events based on checkboxes
    filtered_events = []
    if show_honeypot:
        filtered_events.extend([e for e in events if e.get('honeypot') == True])
    if show_regular:
        filtered_events.extend([e for e in events if not e.get('honeypot')])
    
    if not filtered_events:
        st.info("No events match the selected filters")
        return
    
    events = filtered_events
    
    # Event selector
    event_ids = [e.get('event_id', 'unknown') for e in events]
    selected_event_id = st.selectbox("Select Event", event_ids)
    
    # Find selected event
    selected_event = next((e for e in events if e.get('event_id') == selected_event_id), None)
    
    if not selected_event:
        st.error("Event not found")
        return
    
    # Display event details
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Event Information")
        st.json({
            'Event ID': selected_event.get('event_id'),
            'Timestamp': datetime.fromtimestamp(selected_event.get('timestamp', 0), tz=timezone.utc).isoformat(),
            'Campaign ID': selected_event.get('campaign_id'),
            'Publisher ID': selected_event.get('publisher_id'),
            'IP Address': selected_event.get('ip_address'),
            'Country': selected_event.get('ip_country')
        })
    
    with col2:
        st.subheader("Fraud Analysis")
        is_fraud = selected_event.get('is_fraud', False)
        fraud_score = selected_event.get('fraud_score', 0.0)
        
        st.metric("Fraud Status", "🚨 Fraud Detected" if is_fraud else "✅ Legitimate")
        st.metric("Fraud Score", f"{fraud_score:.4f}")
        st.metric("Fraud Type", selected_event.get('primary_fraud_type', 'unknown'))
    
    # Fraud signals
    if selected_event.get('fraud_signals'):
        st.subheader("Fraud Signals")
        signals = selected_event['fraud_signals']
        if isinstance(signals, list):
            # Display badges in a row
            badge_cols = st.columns(min(len(signals), 5))  # Max 5 columns
            for idx, signal in enumerate(signals):
                with badge_cols[idx % len(badge_cols)]:
                    st.markdown(
                        f'<span style="background-color: #ff4444; color: white; padding: 4px 8px; '
                        f'border-radius: 4px; font-size: 0.9em; font-weight: bold;">🚨 {signal}</span>',
                        unsafe_allow_html=True
                    )
        else:
            st.text(signals)
    
    # AI Explanation
    if selected_event.get('reasoning'):
        st.subheader("🤖 AI Explanation")
        st.info(selected_event['reasoning'])


def _convert_google_ads_api_to_events(
    performance_data: List[Dict[str, Any]],
    keyword_data: List[Dict[str, Any]],
    placement_data: List[Dict[str, Any]],
    hours: int
) -> List[Dict[str, Any]]:
    """
    Convert Google Ads API performance data into event format for display
    
    Args:
        performance_data: Campaign performance data from API
        keyword_data: Keyword performance data from API
        placement_data: Placement performance data from API
        hours: Time range in hours
    
    Returns:
        List of events in format compatible with dashboard
    """
    import random
    events = []
    now = datetime.now(timezone.utc)
    
    # Process performance data (campaign-level)
    for perf in performance_data:
        campaign_id = str(perf.get('campaign_id', ''))
        clicks = perf.get('clicks', 0)
        cost_micros = perf.get('cost_micros', 0)
        avg_cpc_micros = perf.get('avg_cpc_micros', 0)
        date_str = perf.get('date', '')
        timestamp = perf.get('timestamp', int(now.timestamp()))
        
        # Create individual click events from aggregated data
        # Distribute clicks across the day
        total_impressions = perf.get('impressions', 0)
        total_conversions = perf.get('conversions', 0)
        
        for i in range(clicks):
            # Distribute timestamp within the day
            click_offset = random.uniform(0, 1)  # Random time within day
            event_timestamp = int(timestamp - (click_offset * 86400))  # Spread across day
            
            # Generate a mock GCLID for API data (since API doesn't provide individual GCLIDs)
            gclid = f"API-{campaign_id}-{event_timestamp}-{i}"
            
            # Calculate per-click metrics (distribute aggregated values)
            # For impressions, use average per click (since we can't know exact impression per click)
            impressions_per_click = total_impressions / clicks if clicks > 0 else 0
            # For conversions, use probability (conversion rate)
            has_conversion = random.random() < (total_conversions / clicks) if clicks > 0 else False
            # For cost, use average CPC
            click_cost_micros = avg_cpc_micros if avg_cpc_micros > 0 else (cost_micros / clicks if clicks > 0 else 0)
            
            event = {
                'event_id': f'google-ads-api-{campaign_id}-{event_timestamp}-{i}',
                'timestamp': event_timestamp,
                'source': 'google_ads_api',
                'campaign_id': campaign_id,
                'campaign_name': perf.get('campaign_name', ''),
                'gclid': gclid,
                'keyword': '',  # Will be filled from keyword_data if available
                'target_id': '',  # Will be filled from placement_data if available
                'ad_group_id': '',
                'cost_micros': click_cost_micros,
                'clicks': 1,
                'impressions': impressions_per_click,
                'conversions': 1 if has_conversion else 0,
                'ctr': perf.get('ctr', 0.0),
                'is_fraud': False,  # Will be determined by fraud detection data
                'fraud_score': 0.0,  # Will be merged from fraud events
                'primary_fraud_type': 'legitimate',
                'fraud_signals': []
            }
            events.append(event)
    
    # Enhance with keyword data
    keyword_lookup = {}
    for kw in keyword_data:
        key = (str(kw.get('campaign_id', '')), kw.get('date', ''))
        if key not in keyword_lookup:
            keyword_lookup[key] = []
        keyword_lookup[key].append(kw)
    
    # Match events with keywords
    for event in events:
        campaign_id = event.get('campaign_id', '')
        event_date = datetime.fromtimestamp(event.get('timestamp', 0), tz=timezone.utc).strftime('%Y-%m-%d')
        key = (campaign_id, event_date)
        
        if key in keyword_lookup:
            # Assign keyword from matching keyword data (randomly if multiple)
            matching_keywords = keyword_lookup[key]
            if matching_keywords:
                kw = random.choice(matching_keywords)
                event['keyword'] = kw.get('keyword', '')
                event['ad_group_id'] = str(kw.get('ad_group_id', ''))
    
    # Enhance with placement data
    placement_lookup = {}
    for pl in placement_data:
        key = (str(pl.get('campaign_id', '')), pl.get('date', ''))
        if key not in placement_lookup:
            placement_lookup[key] = []
        placement_lookup[key].append(pl)
    
    # Match events with placements
    for event in events:
        campaign_id = event.get('campaign_id', '')
        event_date = datetime.fromtimestamp(event.get('timestamp', 0), tz=timezone.utc).strftime('%Y-%m-%d')
        key = (campaign_id, event_date)
        
        if key in placement_lookup:
            # Assign placement from matching placement data
            matching_placements = placement_lookup[key]
            if matching_placements:
                pl = random.choice(matching_placements)
                event['target_id'] = pl.get('placement_id', '')
                if not event.get('ad_group_id'):
                    event['ad_group_id'] = str(pl.get('ad_group_id', ''))
    
    return events


def _merge_api_data_with_fraud_events(
    api_events: List[Dict[str, Any]],
    fraud_events: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge Google Ads API events with fraud detection events
    
    Args:
        api_events: Events from Google Ads API
        fraud_events: Fraud detection events from DynamoDB
    
    Returns:
        Merged events with fraud information
    """
    # Create lookup for fraud events by campaign_id, keyword, target_id
    fraud_lookup = {}
    for fraud_event in fraud_events:
        key = (
            str(fraud_event.get('campaign_id', '')),
            fraud_event.get('keyword', ''),
            str(fraud_event.get('target_id', ''))
        )
        if key not in fraud_lookup:
            fraud_lookup[key] = []
        fraud_lookup[key].append(fraud_event)
    
    # Merge fraud data into API events
    merged_events = []
    for api_event in api_events:
        # Try to find matching fraud event
        campaign_id = str(api_event.get('campaign_id', ''))
        keyword = api_event.get('keyword', '')
        target_id = str(api_event.get('target_id', ''))
        
        key = (campaign_id, keyword, target_id)
        
        # Find best matching fraud event
        matching_fraud = None
        if key in fraud_lookup and fraud_lookup[key]:
            # Use the most recent fraud event
            matching_fraud = max(fraud_lookup[key], key=lambda x: x.get('timestamp', 0))
        
        # Merge fraud information
        merged_event = api_event.copy()
        if matching_fraud:
            merged_event.update({
                'is_fraud': matching_fraud.get('is_fraud', False),
                'fraud_score': matching_fraud.get('fraud_score', 0.0),
                'primary_fraud_type': matching_fraud.get('primary_fraud_type', 'legitimate'),
                'fraud_signals': matching_fraud.get('fraud_signals', []),
                'reasoning': matching_fraud.get('reasoning', '')
            })
        else:
            # No fraud data available, keep as legitimate
            merged_event.update({
                'is_fraud': False,
                'fraud_score': 0.0,
                'primary_fraud_type': 'legitimate',
                'fraud_signals': []
            })
        
        merged_events.append(merged_event)
    
    # Add fraud events that don't have matching API events
    api_event_keys = set(
        (str(e.get('campaign_id', '')), e.get('keyword', ''), str(e.get('target_id', '')))
        for e in api_events
    )
    
    for fraud_event in fraud_events:
        key = (
            str(fraud_event.get('campaign_id', '')),
            fraud_event.get('keyword', ''),
            str(fraud_event.get('target_id', ''))
        )
        if key not in api_event_keys:
            # This fraud event doesn't have matching API data, add it anyway
            merged_events.append(fraud_event)
    
    # Sort by timestamp descending
    merged_events.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    
    return merged_events


def get_stored_historical_events(
    hours: int,
    campaign_id: Optional[str] = None,
    target_id: Optional[str] = None,
    keyword: Optional[str] = None,
    gclid: Optional[str] = None,
    fraud_threshold: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Get stored historical Google Ads events from DynamoDB
    These are events that were imported from Nov 2023-2024 and shifted forward
    
    Args:
        hours: Number of hours to look back
        campaign_id: Campaign ID filter
        target_id: Target ID filter
        keyword: Keyword filter
        gclid: GCLID search string
        fraud_threshold: Minimum fraud score
    
    Returns:
        List of historical events from DynamoDB
    """
    if not table:
        return []
    
    try:
        # Calculate timestamp range
        now = datetime.now(timezone.utc)
        start_timestamp = int((now - timedelta(hours=hours)).timestamp())
        end_timestamp = int(now.timestamp())
        
        events = []
        
        # Query for historical events (source = 'google_ads_api' or has 'shifted_date')
        # Priority: GCLID > Keyword > Target > Campaign > All
        
        if gclid and gclid.strip():
            events = query_events_by_gclid(TABLE_NAME, gclid.strip(), start_timestamp, end_timestamp)
        elif keyword and keyword != "All" and keyword.strip():
            events = query_events_by_keyword(TABLE_NAME, keyword.strip(), start_timestamp, end_timestamp)
        elif target_id and target_id != "All" and target_id.strip():
            events = query_events_by_target(TABLE_NAME, target_id.strip(), start_timestamp, end_timestamp)
        elif campaign_id and campaign_id != "All":
            events = query_events_by_campaign(TABLE_NAME, campaign_id, start_timestamp, end_timestamp)
        else:
            # Query all events in time range - scan is expensive, so we'll use campaign query if possible
            # For now, return empty and let API fetch handle it
            events = []
        
        # Filter for historical/stored API events
        historical_events = [
            e for e in events 
            if e.get('source') == 'google_ads_api' or 'shifted_date' in e or 'original_date' in e
        ]
        
        # Apply fraud threshold
        if fraud_threshold > 0.0:
            historical_events = [
                e for e in historical_events 
                if float(e.get('fraud_score', 0.0)) >= fraud_threshold
            ]
        
        return historical_events
    
    except Exception as e:
        print(f"Error getting stored historical events: {str(e)}")
        return []


def render_google_ads_view(hours: int):
    """Render Google Ads focused view"""
    st.header("📊 Google Ads Analysis")
    
    # Always use DynamoDB as the data source
    st.success("✅ Using DynamoDB as data source - Showing all Google Ads events from database")
    st.info("💡 All data is pulled from DynamoDB, including historical Google Ads data and real-time tracking events.")
    
    # Check if Google Ads API is available for optimization data
    if 'google_ads_api_checked' not in st.session_state:
        try:
            api_client = get_google_ads_api_client() if get_google_ads_api_client else None
            st.session_state.google_ads_api_available = api_client is not None
            st.session_state.google_ads_api_checked = True
        except:
            st.session_state.google_ads_api_available = False
            st.session_state.google_ads_api_checked = True
    
    api_available = GOOGLE_ADS_API_AVAILABLE and st.session_state.get('google_ads_api_available', False)
    
    # Optimization Data Section (if API is available)
    if api_available and fetch_google_ads_optimization_scores:
        with st.expander("🎯 Optimization Data from Google Ads API", expanded=False):
            st.subheader("Campaign Optimization Scores")
            
            try:
                optimization_scores = fetch_google_ads_optimization_scores()
                if optimization_scores:
                    scores_df = pd.DataFrame(optimization_scores)
                    st.dataframe(scores_df, use_container_width=True, hide_index=True)
                    
                    # Summary metrics
                    scores_with_values = scores_df[scores_df['optimization_score'].notna()] if 'optimization_score' in scores_df.columns else pd.DataFrame()
                    if not scores_with_values.empty:
                        avg_score = scores_with_values['optimization_score'].mean()
                        max_score = scores_with_values['optimization_score'].max()
                        min_score = scores_with_values['optimization_score'].min()
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Average Optimization Score", f"{avg_score:.1f}%")
                        with col2:
                            st.metric("Max Optimization Score", f"{max_score:.1f}%")
                        with col3:
                            st.metric("Min Optimization Score", f"{min_score:.1f}%")
                else:
                    st.info("No optimization scores available")
            except Exception as e:
                st.warning(f"Could not fetch optimization scores: {str(e)}")
            
            st.divider()
            st.subheader("Keyword Quality Scores")
            
            try:
                quality_scores = fetch_google_ads_quality_scores(days=30)
                if quality_scores:
                    # Filter to show top keywords by quality score
                    quality_df = pd.DataFrame(quality_scores)
                    quality_df = quality_df.sort_values('quality_score', ascending=False, na_position='last').head(50)
                    
                    # Select relevant columns for display
                    display_cols = ['campaign_name', 'ad_group_name', 'keyword', 'match_type', 
                                   'quality_score', 'creative_quality_score', 'landing_page_quality_score', 
                                   'expected_ctr', 'impressions', 'clicks', 'ctr', 'conversions']
                    display_cols = [col for col in display_cols if col in quality_df.columns]
                    
                    st.dataframe(quality_df[display_cols], use_container_width=True, hide_index=True)
                    
                    # Quality score distribution
                    if 'quality_score' in quality_df.columns:
                        quality_df_filtered = quality_df[quality_df['quality_score'].notna()]
                        if not quality_df_filtered.empty:
                            avg_quality = quality_df_filtered['quality_score'].mean()
                            st.metric("Average Quality Score", f"{avg_quality:.1f}/10")
                else:
                    st.info("No quality score data available")
            except Exception as e:
                st.warning(f"Could not fetch quality scores: {str(e)}")
            
            st.divider()
            st.subheader("Optimization Recommendations")
            
            try:
                recommendations = fetch_google_ads_recommendations()
                if recommendations:
                    recs_df = pd.DataFrame(recommendations)
                    st.dataframe(recs_df, use_container_width=True, hide_index=True)
                    
                    # Count by recommendation type
                    if 'recommendation_type' in recs_df.columns:
                        rec_counts = recs_df['recommendation_type'].value_counts()
                        st.write("**Recommendations by Type:**")
                        st.bar_chart(rec_counts)
                else:
                    st.info("No recommendations available")
            except Exception as e:
                st.warning(f"Could not fetch recommendations: {str(e)}")
    elif api_available == False:
        st.info("💡 To see optimization data (quality scores, recommendations), configure your Google Ads API credentials.")
    
    # Initialize session state for selected event
    if 'selected_google_ads_event_id' not in st.session_state:
        st.session_state.selected_google_ads_event_id = None
    
    # 1. GCLID Lookup (Top priority)
    st.subheader("🔍 GCLID Lookup")
    gclid_search = st.text_input(
        "Enter GCLID to search...",
        placeholder="Cj0KCQi...",
        key="gclid_search"
    )
    
    # 2. Filters Section (disabled if GCLID provided)
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)
    
    # Get unique values for dropdowns (use max hours for dropdown population)
    max_hours = 168  # 7 days for dropdown options
    campaigns = get_unique_google_ads_campaigns(TABLE_NAME, max_hours)
    targets = get_unique_google_ads_targets(TABLE_NAME, max_hours)
    keywords = get_unique_google_ads_keywords(TABLE_NAME, max_hours)
    
    with col1:
        campaign_options = ["All"] + campaigns
        selected_campaign = st.selectbox(
            "FraudGuard Campaign",
            campaign_options,
            index=0,
            disabled=bool(gclid_search and gclid_search.strip())
        )
    
    with col2:
        target_options = ["All"] + targets
        selected_target = st.selectbox(
            "Google Target/Placement",
            target_options,
            index=0,
            disabled=bool(gclid_search and gclid_search.strip())
        )
    
    with col3:
        keyword_options = ["All"] + keywords
        selected_keyword = st.selectbox(
            "Keyword",
            keyword_options,
            index=0,
            disabled=bool(gclid_search and gclid_search.strip())
        )
    
    # 3. Time Range & Fraud Threshold
    col1, col2 = st.columns(2)
    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["Last Hour", "Last 24 Hours", "Last 7 Days"],
            index=1
        )
        hours_map = {
            "Last Hour": 1,
            "Last 24 Hours": 24,
            "Last 7 Days": 168
        }
        view_hours = hours_map[time_range]
    
    with col2:
        fraud_threshold = st.slider(
            "Fraud Score ≥",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05
        )
    
    # Load Google Ads events from DynamoDB
    with st.spinner("Loading Google Ads events from DynamoDB..."):
        # Always use DynamoDB as the data source
        events = get_google_ads_events(
            hours=view_hours,
            campaign_id=selected_campaign if selected_campaign != "All" else None,
            target_id=selected_target if selected_target != "All" else None,
            keyword=selected_keyword if selected_keyword != "All" else None,
            gclid=gclid_search.strip() if gclid_search and gclid_search.strip() else None,
            fraud_threshold=fraud_threshold
        )
        
        if events:
            # Count events by source for display
            api_source_events = [e for e in events if e.get('source') == 'google_ads_api']
            tracking_events = [e for e in events if e.get('source') == 'google_ads']
            st.info(f"📊 Loaded {len(events)} events from DynamoDB ({len(api_source_events)} historical API events, {len(tracking_events)} tracking events)")
    
    # Show "View in Event Detail" button if GCLID search found results
    if gclid_search and gclid_search.strip() and events:
        if st.button("View in Event Detail", key="view_in_detail"):
            st.session_state.selected_google_ads_event_id = events[0].get('event_id')
            st.session_state.page = "Event Detail"
            st.rerun()
    
    # Data Source Breakdown
    if events:
        st.divider()
        st.subheader("📊 Data Source Breakdown (All from DynamoDB)")
        
        api_source_events = [e for e in events if e.get('source') == 'google_ads_api']
        tracking_events = [e for e in events if e.get('source') == 'google_ads']
        
        api_source_count = len(api_source_events)
        tracking_count = len(tracking_events)
        total_count = len(events)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "📦 Historical API Data",
                f"{api_source_count:,}",
                help="Historical Google Ads data imported from API and stored in DynamoDB"
            )
        
        with col2:
            st.metric(
                "🔄 Real-time Tracking",
                f"{tracking_count:,}",
                help="Real-time tracking events stored in DynamoDB"
            )
        
        with col3:
            st.metric(
                "📈 Total Events",
                f"{total_count:,}",
                help="All events from DynamoDB"
            )
        
        # Show detailed breakdown
        with st.expander("🔍 Detailed Data Source Information", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📦 Historical API Data")
                if api_source_count > 0:
                    # Calculate API metrics
                    api_clicks = api_source_count
                    api_impressions = sum(e.get('impressions', 0) for e in api_source_events if isinstance(e.get('impressions'), (int, float)))
                    api_cost_micros = sum(e.get('cost_micros', 0) for e in api_source_events if isinstance(e.get('cost_micros'), (int, float)))
                    api_conversions = sum(e.get('conversions', 0) for e in api_source_events if isinstance(e.get('conversions'), (int, float)))
                    api_fraud_count = sum(1 for e in api_source_events if e.get('is_fraud', False))
                    
                    st.write(f"**Clicks:** {api_clicks:,}")
                    st.write(f"**Impressions:** {int(api_impressions):,}")
                    st.write(f"**Total Cost:** ${api_cost_micros / 1_000_000:.2f}")
                    st.write(f"**Conversions:** {int(api_conversions):,}")
                    st.write(f"**Fraud Detected:** {api_fraud_count:,} ({api_fraud_count / api_clicks * 100 if api_clicks > 0 else 0:.1f}%)")
                    
                    # Show unique campaigns from API
                    api_campaigns = set(e.get('campaign_id', '') for e in api_source_events if e.get('campaign_id'))
                    if api_campaigns:
                        st.write(f"**Campaigns:** {len(api_campaigns)}")
                        with st.expander("View Campaigns"):
                            for camp_id in sorted(api_campaigns):
                                camp_name = next((e.get('campaign_name', '') for e in api_source_events if e.get('campaign_id') == camp_id), '')
                                st.write(f"- {camp_id}: {camp_name}")
                else:
                    st.info("No historical API data in current view")
            
            with col2:
                st.markdown("### 🔄 Real-time Tracking Events")
                if tracking_count > 0:
                    tracking_fraud_count = sum(1 for e in tracking_events if e.get('is_fraud', False))
                    tracking_legitimate_count = tracking_count - tracking_fraud_count
                    
                    st.write(f"**Total Events:** {tracking_count:,}")
                    st.write(f"**Fraud Detected:** {tracking_fraud_count:,} ({tracking_fraud_count / tracking_count * 100 if tracking_count > 0 else 0:.1f}%)")
                    st.write(f"**Legitimate:** {tracking_legitimate_count:,} ({tracking_legitimate_count / tracking_count * 100 if tracking_count > 0 else 0:.1f}%)")
                    
                    # Show fraud types
                    fraud_types = {}
                    for e in tracking_events:
                        if e.get('is_fraud'):
                            fraud_type = e.get('primary_fraud_type', 'unknown')
                            fraud_types[fraud_type] = fraud_types.get(fraud_type, 0) + 1
                    
                    if fraud_types:
                        st.write("**Fraud Types:**")
                        for fraud_type, count in sorted(fraud_types.items(), key=lambda x: x[1], reverse=True):
                            st.write(f"- {fraud_type}: {count}")
                else:
                    st.info("No DynamoDB events in current view")
        
        # Visual indicator in table
        st.info(f"💡 **Tip:** Events marked with 🌐 are from Google Ads API. Events marked with 💾 are from DynamoDB fraud detection.")
    
    # 4. Event Table
    st.divider()
    st.subheader("Recent Google Ads Events")
    
    if not events:
        st.info("No Google Ads events found matching the filters.")
        return
    
    # Calculate API-specific metrics if available (needed for table display)
    api_events_count = sum(1 for e in events if e.get('source') == 'google_ads_api')
    
    # Prepare data for table
    table_data = []
    for event in events[:1000]:  # Limit to 1000 rows
        timestamp = event.get('timestamp', 0)
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        gclid = event.get('gclid', '')
        gclid_display = gclid[:8] + "..." if len(gclid) > 8 else gclid
        
        # Determine source
        source = event.get('source', 'google_ads')
        source_display = "🌐 API" if source == 'google_ads_api' else "💾 DB"
        
        row_data = {
            'Source': source_display,
            'Timestamp': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'GCLID': gclid_display,
            'Full GCLID': gclid,
            'Campaign': event.get('campaign_name', event.get('campaign_id', '')),
            'Keyword': event.get('keyword', ''),
            'Target': event.get('target_id', ''),
            'Fraud Score': f"{float(event.get('fraud_score', 0.0)):.2f}",
            'Is Fraud': "🚨 Fraud" if event.get('is_fraud', False) else "✅ Legitimate",
            'Event ID': event.get('event_id', ''),
            'Event': event  # Store full event for details
        }
        
        # Add API-specific columns if available
        if source == 'google_ads_api':
            cost_micros = event.get('cost_micros', 0)
            impressions = event.get('impressions', 0)
            conversions = event.get('conversions', 0)
            row_data.update({
                'Cost': f"${cost_micros / 1_000_000:.2f}" if cost_micros > 0 else "$0.00",
                'Impressions': f"{int(impressions):,}" if impressions > 0 else "0",
                'Conversions': f"{int(conversions)}" if conversions > 0 else "0"
            })
        
        table_data.append(row_data)
    
    df = pd.DataFrame(table_data)
    
    # Display table with appropriate columns
    if api_events_count > 0:
        # Show API columns
        display_columns = ['Source', 'Timestamp', 'Campaign', 'Keyword', 'Target', 'Cost', 'Impressions', 'Conversions', 'Fraud Score', 'Is Fraud']
        # Filter to only include columns that exist
        display_columns = [col for col in display_columns if col in df.columns]
        st.dataframe(
            df[display_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        # Standard columns for DynamoDB-only
        display_columns = ['Timestamp', 'GCLID', 'Keyword', 'Target', 'Fraud Score', 'Is Fraud']
        st.dataframe(
            df[display_columns],
            use_container_width=True,
            hide_index=True
        )
    
    # 5. Overview Metrics
    st.divider()
    st.subheader("Overview Metrics")
    
    total_clicks = len(events)
    fraud_count = sum(1 for e in events if e.get('is_fraud', False))
    fraud_rate = (fraud_count / total_clicks * 100) if total_clicks > 0 else 0.0
    blocked_count = sum(1 for e in events if e.get('is_fraud', False) and float(e.get('fraud_score', 0.0)) >= fraud_threshold)
    
    # Calculate API-specific metrics if available
    total_impressions = sum(e.get('impressions', 0) for e in events if isinstance(e.get('impressions'), (int, float)))
    total_cost_micros = sum(e.get('cost_micros', 0) for e in events if isinstance(e.get('cost_micros'), (int, float)))
    total_conversions = sum(e.get('conversions', 0) for e in events if isinstance(e.get('conversions'), (int, float)))
    
    if api_events_count > 0:
        # Show expanded metrics for API data
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Clicks", total_clicks, help="From DynamoDB (Google Ads API source)" if api_events_count > 0 else "From DynamoDB")
        with col2:
            st.metric("Impressions", f"{int(total_impressions):,}", help="From Google Ads API")
        with col3:
            st.metric("Fraud Rate", f"{fraud_rate:.2f}%", delta=f"{fraud_count} events")
        with col4:
            st.metric("Total Cost", f"${total_cost_micros / 1_000_000:.2f}", help="From Google Ads API")
        with col5:
            st.metric("Conversions", int(total_conversions), help="From Google Ads API")
        
        # Additional metrics row
        col1, col2, col3 = st.columns(3)
        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
        conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0.0
        avg_cpc = (total_cost_micros / total_clicks / 1_000_000) if total_clicks > 0 else 0.0
        
        with col1:
            st.metric("CTR", f"{ctr:.2f}%")
        with col2:
            st.metric("Conversion Rate", f"{conversion_rate:.2f}%")
        with col3:
            st.metric("Avg CPC", f"${avg_cpc:.2f}")
    else:
        # Standard metrics for DynamoDB-only data
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Clicks", total_clicks)
        with col2:
            st.metric("Fraud Rate", f"{fraud_rate:.2f}%", delta=f"{fraud_count} events")
        with col3:
            st.metric("Blocked", blocked_count)
    
    # 6. Quick Event Summary (on row selection)
    st.divider()
    st.subheader("Event Details")
    
    # Create selectbox for event selection with source indicator
    event_options = [
        f"{row['Source']} {row['Timestamp']} - {row['GCLID']} ({row['Is Fraud']})" 
        for row in table_data
    ]
    selected_index = st.selectbox("Select event to view details", range(len(event_options)), format_func=lambda x: event_options[x])
    
    if selected_index is not None and selected_index < len(table_data):
        selected_row = table_data[selected_index]
        selected_event = selected_row['Event']
        
        # Show data source badge
        event_source = selected_event.get('source', 'google_ads')
        if event_source == 'google_ads_api':
            st.success("🌐 **Data Source: Google Ads API** - Real-time data from your Google Ads account")
        else:
            st.info("💾 **Data Source: DynamoDB** - Fraud detection event from database")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Event Information**")
            st.write(f"**Event ID:** {selected_event.get('event_id', 'N/A')}")
            st.write(f"**Data Source:** {'🌐 Google Ads API' if event_source == 'google_ads_api' else '💾 DynamoDB'}")
            st.write(f"**Timestamp:** {datetime.fromtimestamp(selected_event.get('timestamp', 0), tz=timezone.utc).isoformat()}")
            st.write(f"**GCLID:** {selected_event.get('gclid', 'N/A')}")
            st.write(f"**Campaign:** {selected_event.get('campaign_name', selected_event.get('campaign_id', 'N/A'))}")
            st.write(f"**Campaign ID:** {selected_event.get('campaign_id', 'N/A')}")
            st.write(f"**Keyword:** {selected_event.get('keyword', 'N/A')}")
            st.write(f"**Target:** {selected_event.get('target_id', 'N/A')}")
            if selected_event.get('ad_group_id'):
                st.write(f"**Ad Group ID:** {selected_event.get('ad_group_id')}")
            
            # Show API-specific data if available
            if event_source == 'google_ads_api':
                st.markdown("---")
                st.write("**Google Ads API Metrics:**")
                cost_micros = selected_event.get('cost_micros', 0)
                impressions = selected_event.get('impressions', 0)
                conversions = selected_event.get('conversions', 0)
                ctr = selected_event.get('ctr', 0.0)
                
                if cost_micros > 0:
                    st.write(f"**Cost:** ${cost_micros / 1_000_000:.2f}")
                if impressions > 0:
                    st.write(f"**Impressions:** {int(impressions):,}")
                if conversions > 0:
                    st.write(f"**Conversions:** {int(conversions)}")
                if ctr > 0:
                    st.write(f"**CTR:** {ctr * 100:.2f}%")
        
        with col2:
            st.write("**Fraud Analysis**")
            is_fraud = selected_event.get('is_fraud', False)
            fraud_score = float(selected_event.get('fraud_score', 0.0))
            st.write(f"**Fraud Status:** {'🚨 Fraud Detected' if is_fraud else '✅ Legitimate'}")
            st.write(f"**Fraud Score:** {fraud_score:.4f}")
            st.write(f"**Fraud Type:** {selected_event.get('primary_fraud_type', 'legitimate' if not is_fraud else 'unknown')}")
            
            # Show fraud signals if available
            fraud_signals = selected_event.get('fraud_signals', [])
            if fraud_signals:
                st.write("**Fraud Signals:**")
                if isinstance(fraud_signals, list):
                    for signal in fraud_signals:
                        st.write(f"- 🚨 {signal}")
                else:
                    st.write(f"- {fraud_signals}")
            
            # Show reasoning if available
            reasoning = selected_event.get('reasoning', '')
            if reasoning:
                st.markdown("---")
                st.write("**AI Reasoning:**")
                st.caption(reasoning)
        
        # View Full Details button
        if st.button("View Full Details", key="view_full_details"):
            st.session_state.selected_google_ads_event_id = selected_event.get('event_id')
            st.session_state.page = "Event Detail"
            st.rerun()
    
    # 7. Fraud-Adjusted Performance Metrics
    st.divider()
    st.subheader("Fraud-Adjusted Performance Metrics")
    
    if events:
        # Calculate fraud-adjusted metrics
        total_cost = len(events) * 0.50  # Assuming $0.50 per click
        fraud_cost = sum(0.50 for e in events if e.get('is_fraud', False))
        legitimate_clicks = total_clicks - fraud_count
        revenue_per_click = 2.0  # Mock revenue per legitimate click
        total_revenue = legitimate_clicks * revenue_per_click
        roas = (total_revenue / total_cost) if total_cost > 0 else 0.0
        cpa = (total_cost / legitimate_clicks) if legitimate_clicks > 0 else 0.0
        wasted_spend = fraud_cost
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ROAS", f"${roas:.2f}")
        with col2:
            st.metric("CPA", f"${cpa:.2f}")
        with col3:
            st.metric("Wasted Spend", f"${wasted_spend:.2f}", delta="↑0.0%")
        with col4:
            ctr = (total_clicks / 1000) * 100 if total_clicks > 0 else 0.0  # Mock CTR
            st.metric("CTR", f"{ctr:.2f}%")
        
        with st.expander("> View Detailed Fraud-Adjusted Metrics", expanded=False):
            st.write("**Detailed Metrics:**")
            st.write(f"- Total Cost: ${total_cost:.2f}")
            st.write(f"- Fraud Cost: ${fraud_cost:.2f}")
            st.write(f"- Legitimate Clicks: {legitimate_clicks}")
            st.write(f"- Total Revenue: ${total_revenue:.2f}")
            st.write(f"- Wasted Spend %: {(wasted_spend / total_cost * 100) if total_cost > 0 else 0:.2f}%")
    
    # 8. Historical Fraud Analysis
    st.divider()
    st.subheader("Historical Fraud Analysis")
    
    # Generate historical data for different periods
    periods = [30, 60, 90]
    historical_data = []
    
    for days in periods:
        # Get events for this period (using mock data scaled to period)
        period_events = get_google_ads_events(
            hours=days * 24,
            campaign_id=selected_campaign if selected_campaign != "All" else None,
            target_id=selected_target if selected_target != "All" else None,
            keyword=selected_keyword if selected_keyword != "All" else None,
            gclid=None,
            fraud_threshold=0.0
        )
        
        period_total = len(period_events)
        period_fraud = sum(1 for e in period_events if e.get('is_fraud', False))
        period_fraud_rate = (period_fraud / period_total * 100) if period_total > 0 else 0.0
        period_cost = period_total * 0.50
        period_wasted = period_fraud * 0.50
        period_avg_fraud_score = sum(float(e.get('fraud_score', 0.0)) for e in period_events) / period_total if period_total > 0 else 0.0
        
        historical_data.append({
            'Period': f"{days} Days",
            'Data Points': period_total,
            'Total Cost': period_cost,
            'Total Wasted Spend': period_wasted,
            'Average Fraud Score': period_avg_fraud_score,
            'Fraud Rate': period_fraud_rate,
            'Wasted Spend %': (period_wasted / period_cost * 100) if period_cost > 0 else 0.0
        })
    
    # Display period metrics
    col1, col2, col3 = st.columns(3)
    for i, days in enumerate(periods):
        with [col1, col2, col3][i]:
            data = historical_data[i]
            st.metric(
                f"{days}-Day Period",
                f"{data['Data Points']} days",
                delta=f"↑{data['Fraud Rate']:.1f}% fraud rate"
            )
    
    # Period Comparison Table
    st.subheader("Period Comparison")
    historical_df = pd.DataFrame(historical_data)
    st.dataframe(
        historical_df,
        use_container_width=True,
        hide_index=True
    )
    
    # 9. Cumulative Impact
    st.divider()
    st.subheader("Cumulative Impact")
    
    total_wasted_all_time = sum(d['Total Wasted Spend'] for d in historical_data)
    total_cost_all_time = sum(d['Total Cost'] for d in historical_data)
    wasted_percentage = (total_wasted_all_time / total_cost_all_time * 100) if total_cost_all_time > 0 else 0.0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Wasted Spend", f"${total_wasted_all_time:.2f}")
    with col2:
        st.metric("Total Cost", f"${total_cost_all_time:,.2f}")
    with col3:
        st.metric("Wasted Spend %", f"{wasted_percentage:.2f}%")
    with col4:
        st.metric("Trend", "Stable", delta="→")
    
    # 10. Fraud Rate Trend Chart
    st.subheader("Fraud Rate Trend")
    if historical_data:
        trend_df = pd.DataFrame({
            'Period': [d['Period'] for d in historical_data],
            'Fraud Rate (%)': [d['Fraud Rate'] for d in historical_data]
        })
        fig = px.line(
            trend_df,
            x='Period',
            y='Fraud Rate (%)',
            title="Fraud Rate Over Time",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 11. Optimization Recommendations
    st.divider()
    st.subheader("Optimization Recommendations")
    
    # Budget Reallocation Recommendations
    st.write("**Budget Reallocation Recommendations:**")
    budget_recs = pd.DataFrame({
        'Date': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        'Current Budget': ['$0.00'],
        'Recommended Budget': ['$0.00'],
        'Change': ['+0.0%'],
        'Status': ['Pending'],
        'Reason': ['N/A']
    })
    st.dataframe(budget_recs, use_container_width=True, hide_index=True)
    
    # Bid Adjustment Recommendations
    st.write("**Bid Adjustment Recommendations:**")
    bid_recs = pd.DataFrame({
        'Date': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        'Current Bid': ['$0.00'],
        'Recommended Bid': ['$0.00'],
        'Change': ['+0.0%'],
        'Status': ['Pending'],
        'Reason': ['N/A']
    })
    st.dataframe(bid_recs, use_container_width=True, hide_index=True)
    
    # 12. Fraud Remediation Actions
    st.divider()
    st.subheader("Fraud Remediation Actions")
    st.info("No remediation actions taken for this campaign.")
    
    # 13. AI-Powered Fraud Recommendations
    st.divider()
    st.subheader("AI-Powered Fraud Recommendations")
    st.info("No AI recommendations available for this campaign. Run the AI recommendations module to generate strategies.")
    
    # 14. Export Functionality
    st.divider()
    st.subheader("Export for Google Refund")
    
    if events:
        # Prepare CSV data
        csv_data = []
        for event in events:
            timestamp = event.get('timestamp', 0)
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            csv_data.append({
                'Date/Time': dt.isoformat(),
                'GCLID': event.get('gclid', ''),
                'Campaign ID': event.get('campaign_id', ''),
                'Ad Group ID': event.get('ad_group_id', ''),
                'Keyword': event.get('keyword', ''),
                'Target ID': event.get('target_id', ''),
                'Fraud Score': f"{float(event.get('fraud_score', 0.0)):.4f}",
                'Is Fraud': 'Yes' if event.get('is_fraud', False) else 'No'
            })
        
        csv_df = pd.DataFrame(csv_data)
        
        # Convert to CSV
        csv_buffer = io.StringIO()
        csv_df.to_csv(csv_buffer, index=False)
        csv_string = csv_buffer.getvalue()
        
        st.download_button(
            label="📥 Export for Google Refund",
            data=csv_string,
            file_name=f"google_ads_refund_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Export filtered events in CSV format for Google's Click Quality Form"
        )
        
        st.info(f"Export will include {len(events)} event(s) matching current filters.")
    else:
        st.info("No events to export. Adjust filters to see events.")


def main():
    """Main dashboard function"""
    # Sidebar
    with st.sidebar:
        st.title("🛡️ FraudGuard AI")
        st.markdown("---")
        
        # Time range selector
        time_range = st.selectbox(
            "Time Range",
            ["Last Hour", "Last 24 Hours", "Last 7 Days"],
            index=1
        )
        
        hours_map = {
            "Last Hour": 1,
            "Last 24 Hours": 24,
            "Last 7 Days": 168
        }
        hours = hours_map[time_range]
        
        # Cost Configuration
        st.markdown("### Cost Configuration")
        if 'cost_per_click' not in st.session_state:
            st.session_state.cost_per_click = 0.50
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            cost_per_click = st.number_input(
                "Cost per Click ($)",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.cost_per_click,
                step=0.01,
                format="%.2f",
                key="cost_input"
            )
            st.session_state.cost_per_click = cost_per_click
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            if st.button("➕", help="Increase", key="increase_cost"):
                st.session_state.cost_per_click = min(100.0, st.session_state.cost_per_click + 0.01)
                st.rerun()
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacing
            if st.button("➖", help="Decrease", key="decrease_cost"):
                st.session_state.cost_per_click = max(0.0, st.session_state.cost_per_click - 0.01)
                st.rerun()
        
        cost_per_click = st.session_state.cost_per_click
        
        # Refresh button
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Navigation")
        page = st.radio(
            "Select View",
            ["Real-Time Overview", "Campaign Analysis", "Event Detail", "Google Ads View"],
            index=0
        )
    
    # Load data (only for non-Google Ads views)
    if page != "Google Ads View":
        with st.spinner("Loading events..."):
            events = get_recent_events(hours)
            metrics = calculate_metrics(events, cost_per_click)
    
    # Render selected page
    if page == "Real-Time Overview":
        render_real_time_overview(events, metrics, cost_per_click)
    elif page == "Campaign Analysis":
        render_campaign_analysis(events, metrics)
    elif page == "Event Detail":
        # Check if we should pre-select an event from Google Ads view
        if 'selected_google_ads_event_id' in st.session_state and st.session_state.selected_google_ads_event_id:
            # Filter events to show the selected one
            selected_id = st.session_state.selected_google_ads_event_id
            filtered_events = [e for e in events if e.get('event_id') == selected_id]
            if filtered_events:
                # Temporarily override events to show selected one
                render_event_detail(filtered_events)
                # Clear the selection after showing
                st.session_state.selected_google_ads_event_id = None
            else:
                render_event_detail(events)
        else:
            render_event_detail(events)
    elif page == "Google Ads View":
        render_google_ads_view(hours)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>FraudGuard AI Dashboard | "
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

# Test deployment trigger
