"""
Google Ads API Client
Handles authentication and API calls to Google Ads
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


class GoogleAdsAPIClient:
    """Client for interacting with Google Ads API"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Google Ads API client
        
        Args:
            credentials_path: Path to Google Ads API credentials file (yaml or json)
                             If None, looks for GOOGLE_ADS_CREDENTIALS env var or default paths
        """
        self.client = None
        self.customer_id = None
        
        # Try to find credentials
        if credentials_path:
            self.credentials_path = credentials_path
        elif os.environ.get('GOOGLE_ADS_CREDENTIALS'):
            self.credentials_path = os.environ.get('GOOGLE_ADS_CREDENTIALS')
        elif os.path.exists('google-ads.yaml'):
            self.credentials_path = 'google-ads.yaml'
        elif os.path.exists('.google-ads.yaml'):
            self.credentials_path = '.google-ads.yaml'
        elif os.path.exists('google_ads_credentials.json'):
            self.credentials_path = 'google_ads_credentials.json'
        else:
            raise ValueError(
                "Google Ads credentials not found. Please provide credentials_path or set GOOGLE_ADS_CREDENTIALS env var"
            )
        
        # Initialize client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Ads API client with credentials"""
        try:
            self.client = GoogleAdsClient.load_from_storage(self.credentials_path)
            # Get customer ID from credentials or env
            self.customer_id = os.environ.get('GOOGLE_ADS_CUSTOMER_ID') or self.client.login_customer_id
            if not self.customer_id:
                raise ValueError("GOOGLE_ADS_CUSTOMER_ID must be set in environment or credentials")
        except Exception as e:
            raise ValueError(f"Failed to initialize Google Ads client: {str(e)}")
    
    def get_campaigns(self) -> List[Dict[str, Any]]:
        """
        Get all campaigns from Google Ads account
        
        Returns:
            List of campaign dictionaries with id, name, status, etc.
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        campaigns = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = """
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    campaign.start_date,
                    campaign.end_date,
                    campaign_budget.amount_micros,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr,
                    metrics.average_cpc
                FROM campaign
                WHERE campaign.status != 'REMOVED'
                ORDER BY campaign.id
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                campaign = {
                    'campaign_id': str(row.campaign.id),
                    'name': row.campaign.name,
                    'status': row.campaign.status.name,
                    'channel_type': row.campaign.advertising_channel_type.name,
                    'start_date': row.campaign.start_date if hasattr(row.campaign, 'start_date') else None,
                    'end_date': row.campaign.end_date if hasattr(row.campaign, 'end_date') else None,
                    'budget_micros': row.campaign_budget.amount_micros if hasattr(row, 'campaign_budget') else 0,
                    'impressions': row.metrics.impressions if hasattr(row, 'metrics') else 0,
                    'clicks': row.metrics.clicks if hasattr(row, 'metrics') else 0,
                    'cost_micros': row.metrics.cost_micros if hasattr(row, 'metrics') else 0,
                    'conversions': row.metrics.conversions if hasattr(row, 'metrics') else 0,
                    'ctr': row.metrics.ctr if hasattr(row, 'metrics') else 0.0,
                    'avg_cpc_micros': row.metrics.average_cpc if hasattr(row, 'metrics') else 0
                }
                campaigns.append(campaign)
        
        except GoogleAdsException as ex:
            error = ex.error.code().name
            message = ex.error.message()
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return campaigns
    
    def get_campaign_performance(
        self,
        campaign_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get campaign performance metrics
        
        Args:
            campaign_id: Optional campaign ID to filter (None for all campaigns)
            start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
            end_date: End date in YYYY-MM-DD format (default: today)
        
        Returns:
            List of performance data dictionaries
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        # Default date range: last 30 days
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
        
        campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
        
        performance_data = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr,
                    metrics.average_cpc,
                    metrics.search_impression_share,
                    metrics.search_rank_lost_impression_share
                FROM campaign
                WHERE campaign.status != 'REMOVED'
                  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
                  {campaign_filter}
                ORDER BY campaign.id, segments.date
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                data = {
                    'campaign_id': str(row.campaign.id),
                    'campaign_name': row.campaign.name,
                    'date': row.segments.date,
                    'impressions': row.metrics.impressions if hasattr(row, 'metrics') else 0,
                    'clicks': row.metrics.clicks if hasattr(row, 'metrics') else 0,
                    'cost_micros': row.metrics.cost_micros if hasattr(row, 'metrics') else 0,
                    'conversions': row.metrics.conversions if hasattr(row, 'metrics') else 0,
                    'ctr': row.metrics.ctr if hasattr(row, 'metrics') else 0.0,
                    'avg_cpc_micros': row.metrics.average_cpc if hasattr(row, 'metrics') else 0,
                    'impression_share': row.metrics.search_impression_share if hasattr(row, 'metrics') else 0.0,
                    'rank_lost_impression_share': row.metrics.search_rank_lost_impression_share if hasattr(row, 'metrics') else 0.0
                }
                performance_data.append(data)
        
        except GoogleAdsException as ex:
            error = ex.error.code().name
            message = ex.error.message()
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return performance_data
    
    def get_keywords_performance(
        self,
        campaign_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get keyword performance metrics
        
        Args:
            campaign_id: Optional campaign ID to filter
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            List of keyword performance data
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
        
        campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
        
        keywords_data = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    ad_group.id,
                    ad_group.name,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr,
                    metrics.average_cpc,
                    metrics.quality_score
                FROM keyword_view
                WHERE campaign.status != 'REMOVED'
                  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
                  {campaign_filter}
                ORDER BY campaign.id, segments.date, metrics.clicks DESC
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                data = {
                    'campaign_id': str(row.campaign.id),
                    'campaign_name': row.campaign.name,
                    'ad_group_id': str(row.ad_group.id),
                    'ad_group_name': row.ad_group.name,
                    'keyword': row.ad_group_criterion.keyword.text if hasattr(row, 'ad_group_criterion') else '',
                    'match_type': row.ad_group_criterion.keyword.match_type.name if hasattr(row, 'ad_group_criterion') else '',
                    'date': row.segments.date,
                    'impressions': row.metrics.impressions if hasattr(row, 'metrics') else 0,
                    'clicks': row.metrics.clicks if hasattr(row, 'metrics') else 0,
                    'cost_micros': row.metrics.cost_micros if hasattr(row, 'metrics') else 0,
                    'conversions': row.metrics.conversions if hasattr(row, 'metrics') else 0,
                    'ctr': row.metrics.ctr if hasattr(row, 'metrics') else 0.0,
                    'avg_cpc_micros': row.metrics.average_cpc if hasattr(row, 'metrics') else 0,
                    'quality_score': row.metrics.quality_score if hasattr(row, 'metrics') else 0
                }
                keywords_data.append(data)
        
        except GoogleAdsException as ex:
            error = ex.error.code().name
            message = ex.error.message()
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return keywords_data
    
    def get_placements_performance(
        self,
        campaign_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get placement/target performance metrics
        
        Args:
            campaign_id: Optional campaign ID to filter
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            List of placement performance data
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
        
        campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
        
        placements_data = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    ad_group.id,
                    ad_group.name,
                    ad_group_criterion.placement.url,
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.ctr,
                    metrics.average_cpc
                FROM placement_view
                WHERE campaign.status != 'REMOVED'
                  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
                  {campaign_filter}
                ORDER BY campaign.id, segments.date, metrics.clicks DESC
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                placement_url = row.ad_group_criterion.placement.url if hasattr(row, 'ad_group_criterion') else ''
                # Extract domain/placement ID from URL
                placement_id = placement_url.split('/')[2] if placement_url else ''
                
                data = {
                    'campaign_id': str(row.campaign.id),
                    'campaign_name': row.campaign.name,
                    'ad_group_id': str(row.ad_group.id),
                    'ad_group_name': row.ad_group.name,
                    'placement_url': placement_url,
                    'placement_id': placement_id,
                    'date': row.segments.date,
                    'impressions': row.metrics.impressions if hasattr(row, 'metrics') else 0,
                    'clicks': row.metrics.clicks if hasattr(row, 'metrics') else 0,
                    'cost_micros': row.metrics.cost_micros if hasattr(row, 'metrics') else 0,
                    'conversions': row.metrics.conversions if hasattr(row, 'metrics') else 0,
                    'ctr': row.metrics.ctr if hasattr(row, 'metrics') else 0.0,
                    'avg_cpc_micros': row.metrics.average_cpc if hasattr(row, 'metrics') else 0
                }
                placements_data.append(data)
        
        except GoogleAdsException as ex:
            error = ex.error.code().name
            message = ex.error.message()
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return placements_data

