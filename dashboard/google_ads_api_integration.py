"""
Google Ads API Integration for Dashboard
Pulls real data from Google Ads API and integrates with fraud detection data
"""
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.google_ads_api.client import GoogleAdsAPIClient
    GOOGLE_ADS_API_AVAILABLE = True
except ImportError:
    GOOGLE_ADS_API_AVAILABLE = False
    GoogleAdsAPIClient = None


def get_google_ads_api_client() -> Optional[GoogleAdsAPIClient]:
    """
    Get initialized Google Ads API client if credentials are available
    
    Returns:
        GoogleAdsAPIClient instance or None if not available
    """
    if not GOOGLE_ADS_API_AVAILABLE:
        return None
    
    try:
        client = GoogleAdsAPIClient()
        return client
    except Exception as e:
        print(f"Warning: Could not initialize Google Ads API client: {str(e)}")
        return None


def fetch_google_ads_campaigns() -> List[Dict[str, Any]]:
    """
    Fetch campaigns from Google Ads API
    
    Returns:
        List of campaign dictionaries
    """
    client = get_google_ads_api_client()
    if not client:
        return []
    
    try:
        campaigns = client.get_campaigns()
        return campaigns
    except Exception as e:
        print(f"Error fetching Google Ads campaigns: {str(e)}")
        return []


def fetch_google_ads_performance(
    campaign_id: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Fetch campaign performance data from Google Ads API
    
    Args:
        campaign_id: Optional campaign ID to filter
        days: Number of days to look back
    
    Returns:
        List of performance data dictionaries
    """
    client = get_google_ads_api_client()
    if not client:
        return []
    
    try:
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        performance = client.get_campaign_performance(
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date
        )
        return performance
    except Exception as e:
        print(f"Error fetching Google Ads performance: {str(e)}")
        return []


def fetch_google_ads_keywords(
    campaign_id: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Fetch keyword performance data from Google Ads API
    
    Args:
        campaign_id: Optional campaign ID to filter
        days: Number of days to look back
    
    Returns:
        List of keyword performance data
    """
    client = get_google_ads_api_client()
    if not client:
        return []
    
    try:
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        keywords = client.get_keywords_performance(
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date
        )
        return keywords
    except Exception as e:
        print(f"Error fetching Google Ads keywords: {str(e)}")
        return []


def fetch_google_ads_placements(
    campaign_id: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Fetch placement/target performance data from Google Ads API
    
    Args:
        campaign_id: Optional campaign ID to filter
        days: Number of days to look back
    
    Returns:
        List of placement performance data
    """
    client = get_google_ads_api_client()
    if not client:
        return []
    
    try:
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        
        placements = client.get_placements_performance(
            campaign_id=campaign_id,
            start_date=start_date,
            end_date=end_date
        )
        return placements
    except Exception as e:
        print(f"Error fetching Google Ads placements: {str(e)}")
        return []


def merge_google_ads_with_fraud_data(
    google_ads_data: List[Dict[str, Any]],
    fraud_events: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge Google Ads API data with fraud detection events
    
    Args:
        google_ads_data: Performance data from Google Ads API
        fraud_events: Fraud detection events from DynamoDB
    
    Returns:
        Merged data with fraud information
    """
    # Create lookup for fraud events by campaign_id, keyword, target_id
    fraud_lookup = {}
    for event in fraud_events:
        key = (
            event.get('campaign_id'),
            event.get('keyword'),
            event.get('target_id')
        )
        if key not in fraud_lookup:
            fraud_lookup[key] = []
        fraud_lookup[key].append(event)
    
    # Merge data
    merged = []
    for ads_data in google_ads_data:
        campaign_id = str(ads_data.get('campaign_id', ''))
        keyword = ads_data.get('keyword', '')
        placement_id = ads_data.get('placement_id', '')
        
        # Find matching fraud events
        matching_fraud = []
        for key, events in fraud_lookup.items():
            if (str(key[0]) == campaign_id and 
                (not keyword or key[1] == keyword) and
                (not placement_id or str(key[2]) == placement_id)):
                matching_fraud.extend(events)
        
        # Calculate fraud metrics
        fraud_count = sum(1 for e in matching_fraud if e.get('is_fraud', False))
        total_fraud_events = len(matching_fraud)
        fraud_rate = (fraud_count / total_fraud_events * 100) if total_fraud_events > 0 else 0.0
        avg_fraud_score = (
            sum(float(e.get('fraud_score', 0.0)) for e in matching_fraud) / total_fraud_events
            if total_fraud_events > 0 else 0.0
        )
        
        # Add fraud metrics to Google Ads data
        merged_data = ads_data.copy()
        merged_data.update({
            'fraud_events_count': total_fraud_events,
            'fraud_count': fraud_count,
            'fraud_rate': fraud_rate,
            'avg_fraud_score': avg_fraud_score,
            'fraud_cost_micros': int(fraud_count * ads_data.get('avg_cpc_micros', 0)),
            'wasted_spend_micros': int(fraud_count * ads_data.get('avg_cpc_micros', 0))
        })
        merged.append(merged_data)
    
    return merged

