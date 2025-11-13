"""
Google Ads API Client
Handles authentication and API calls to Google Ads
"""
import os
import json
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Try to import AWS secrets helper
try:
    from .aws_secrets import get_google_ads_credentials
    AWS_SECRETS_AVAILABLE = True
except ImportError:
    AWS_SECRETS_AVAILABLE = False
    get_google_ads_credentials = None


class GoogleAdsAPIClient:
    """Client for interacting with Google Ads API"""
    
    def __init__(self, credentials_path: Optional[str] = None, prefer_aws: bool = True):
        """
        Initialize Google Ads API client
        
        Args:
            credentials_path: Path to Google Ads API credentials file (yaml or json)
                             If None, tries multiple sources in order:
                             1. AWS Secrets Manager (if prefer_aws=True)
                             2. AWS Parameter Store
                             3. Environment variables
                             4. Local file (google-ads.yaml)
            prefer_aws: If True, prefer AWS services (Secrets Manager/Parameter Store) over local files
        """
        self.client = None
        self.customer_id = None
        self.credentials_path = None
        self._temp_credentials_file = None
        
        # Try to find credentials
        if credentials_path:
            # Explicit path provided
            self.credentials_path = credentials_path
        elif AWS_SECRETS_AVAILABLE and get_google_ads_credentials:
            # Try AWS Secrets Manager / Parameter Store / Environment
            credentials_dict = get_google_ads_credentials(prefer_aws=prefer_aws)
            if credentials_dict:
                # Create temporary YAML file from credentials dict
                self._temp_credentials_file = self._create_temp_credentials_file(credentials_dict)
                self.credentials_path = self._temp_credentials_file.name
            else:
                # Fall back to local file search
                self.credentials_path = self._find_local_credentials_file()
        else:
            # No AWS support, try local files
            self.credentials_path = self._find_local_credentials_file()
        
        if not self.credentials_path:
            raise ValueError(
                "Google Ads credentials not found. Please:\n"
                "1. Create secrets.json file with google_ads section, OR\n"
                "2. Create google-ads.yaml file, OR\n"
                "3. Set environment variables (GOOGLE_ADS_DEVELOPER_TOKEN, etc.), OR\n"
                "4. Store credentials in AWS Secrets Manager (secret name: fraudguard/google-ads-api-credentials)\n"
                "\nSee secrets.json.example for the required format."
            )
        
        # Initialize client
        self._initialize_client()
    
    def _find_local_credentials_file(self) -> Optional[str]:
        """Find local credentials file in common locations"""
        # Get current directory and search up to 3 levels up
        current_dir = os.getcwd()
        search_dirs = [current_dir]
        
        # Add parent directories (up to 3 levels up)
        parent = os.path.dirname(current_dir)
        for _ in range(3):
            if parent and parent != current_dir:
                search_dirs.append(parent)
                parent = os.path.dirname(parent)
            else:
                break
        
        # First try secrets.json in current and parent directories
        for search_dir in search_dirs:
            for secrets_json_name in ['secrets.json', '.secrets.json']:
                secrets_json_path = os.path.join(search_dir, secrets_json_name)
                if os.path.exists(secrets_json_path):
                    # Create temporary YAML from secrets.json
                    credentials_dict = self._load_from_secrets_json(secrets_json_path)
                    if credentials_dict:
                        self._temp_credentials_file = self._create_temp_credentials_file(credentials_dict)
                        return self._temp_credentials_file.name
        
        # Fall back to other locations
        possible_paths = [
            os.environ.get('GOOGLE_ADS_CREDENTIALS'),
            'google-ads.yaml',
            '.google-ads.yaml',
            os.path.join(os.path.expanduser('~'), '.google-ads.yaml'),
            'google_ads_credentials.json',
        ]
        
        # Also check parent directories for YAML files
        for search_dir in search_dirs:
            for yaml_name in ['google-ads.yaml', '.google-ads.yaml']:
                yaml_path = os.path.join(search_dir, yaml_name)
                if os.path.exists(yaml_path):
                    possible_paths.append(yaml_path)
        
        for path in possible_paths:
            if path and os.path.exists(path):
                return path
        
        return None
    
    def _load_from_secrets_json(self, secrets_path: str) -> Optional[Dict[str, Any]]:
        """Load Google Ads credentials from secrets.json file"""
        try:
            with open(secrets_path, 'r') as f:
                secrets = json.load(f)
            
            # Try nested structure first (google_ads key), then flat structure
            google_ads = secrets.get('google_ads', {})
            if not google_ads:
                # Fallback to flat structure (for .secrets.json compatibility)
                google_ads = secrets
            
            # Handle customer_id vs login_customer_id
            login_customer_id = google_ads.get('login_customer_id') or google_ads.get('customer_id')
            
            # Check if all required fields are present and not empty
            required_fields = ['developer_token', 'client_id', 'client_secret', 'refresh_token']
            if not all(google_ads.get(field) for field in required_fields):
                return None
            
            if not login_customer_id:
                return None
            
            # Return credentials in the format expected by Google Ads client
            credentials = {
                'developer_token': google_ads['developer_token'],
                'client_id': google_ads['client_id'],
                'client_secret': google_ads['client_secret'],
                'refresh_token': google_ads['refresh_token'],
                'login_customer_id': login_customer_id,
                'use_proto_plus': google_ads.get('use_proto_plus', True)  # Add required setting
            }
            
            return credentials
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"Error loading secrets.json: {e}")
            return None
    
    def _create_temp_credentials_file(self, credentials: Dict[str, Any]) -> tempfile.NamedTemporaryFile:
        """Create temporary YAML file from credentials dictionary"""
        import yaml
        
        # Ensure login_customer_id is set
        if 'login_customer_id' not in credentials and 'customer_id' in credentials:
            credentials['login_customer_id'] = credentials['customer_id']
        
        # Add required use_proto_plus setting if not present
        if 'use_proto_plus' not in credentials:
            credentials['use_proto_plus'] = True
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.yaml',
            delete=False,
            prefix='google-ads-credentials-'
        )
        
        # Write YAML content
        yaml.dump(credentials, temp_file, default_flow_style=False)
        temp_file.close()
        
        return temp_file
    
    def __del__(self):
        """Clean up temporary credentials file if created"""
        if self._temp_credentials_file and os.path.exists(self._temp_credentials_file.name):
            try:
                os.unlink(self._temp_credentials_file.name)
            except Exception:
                pass  # Ignore cleanup errors
    
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
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
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
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
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
                    metrics.average_cpc
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
                    'avg_cpc_micros': row.metrics.average_cpc if hasattr(row, 'metrics') else 0
                }
                keywords_data.append(data)
        
        except GoogleAdsException as ex:
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
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
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return placements_data
    
    def get_click_details(
        self,
        date: str,
        campaign_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get detailed click-level data from ClickView resource
        Includes individual GCLIDs and click details
        
        IMPORTANT LIMITATIONS:
        - Only available for dates within the last 90 days
        - Must query one day at a time (date filter required)
        - Does not include conversion information
        
        Args:
            date: Date in YYYY-MM-DD format (must be within last 90 days)
            campaign_id: Optional campaign ID to filter
        
        Returns:
            List of click detail dictionaries with GCLIDs
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        campaign_filter = f"AND click_view.campaign.id = {campaign_id}" if campaign_id else ""
        
        click_data = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    click_view.gclid,
                    click_view.campaign.id,
                    click_view.campaign.name,
                    click_view.ad_group.id,
                    click_view.ad_group.name,
                    click_view.keyword.info.text,
                    click_view.keyword.info.match_type,
                    click_view.area_of_interest.city,
                    click_view.area_of_interest.country_region,
                    click_view.area_of_interest.metro_area,
                    click_view.location_of_presence.city,
                    click_view.location_of_presence.country_region,
                    click_view.location_of_presence.metro_area,
                    click_view.page_number,
                    click_view.slot,
                    segments.date,
                    segments.hour
                FROM click_view
                WHERE segments.date = '{date}'
                  {campaign_filter}
                ORDER BY segments.date, segments.hour, click_view.gclid
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                # Get GCLID - this is the key field we need!
                gclid = row.click_view.gclid if hasattr(row, 'click_view') and hasattr(row.click_view, 'gclid') else ''
                
                # Build timestamp from date and hour
                date_str = row.segments.date if hasattr(row, 'segments') else date
                hour = row.segments.hour if hasattr(row, 'segments') and hasattr(row.segments, 'hour') else 12
                
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').replace(
                        hour=int(hour),
                        minute=0,
                        second=0,
                        tzinfo=timezone.utc
                    )
                    timestamp = int(date_obj.timestamp())
                except:
                    timestamp = int(datetime.now(timezone.utc).timestamp())
                
                data = {
                    'gclid': gclid,
                    'campaign_id': str(row.click_view.campaign.id) if hasattr(row, 'click_view') and hasattr(row.click_view, 'campaign') else '',
                    'campaign_name': row.click_view.campaign.name if hasattr(row, 'click_view') and hasattr(row.click_view, 'campaign') else '',
                    'ad_group_id': str(row.click_view.ad_group.id) if hasattr(row, 'click_view') and hasattr(row.click_view, 'ad_group') else '',
                    'ad_group_name': row.click_view.ad_group.name if hasattr(row, 'click_view') and hasattr(row.click_view, 'ad_group') else '',
                    'keyword': row.click_view.keyword.info.text if hasattr(row, 'click_view') and hasattr(row.click_view, 'keyword') else '',
                    'match_type': row.click_view.keyword.info.match_type.name if hasattr(row, 'click_view') and hasattr(row.click_view, 'keyword') and hasattr(row.click_view.keyword.info, 'match_type') else '',
                    'city_interest': row.click_view.area_of_interest.city if hasattr(row, 'click_view') and hasattr(row.click_view, 'area_of_interest') else '',
                    'country_interest': row.click_view.area_of_interest.country_region if hasattr(row, 'click_view') and hasattr(row.click_view, 'area_of_interest') else '',
                    'metro_interest': row.click_view.area_of_interest.metro_area if hasattr(row, 'click_view') and hasattr(row.click_view, 'area_of_interest') else '',
                    'city_location': row.click_view.location_of_presence.city if hasattr(row, 'click_view') and hasattr(row.click_view, 'location_of_presence') else '',
                    'country_location': row.click_view.location_of_presence.country_region if hasattr(row, 'click_view') and hasattr(row.click_view, 'location_of_presence') else '',
                    'metro_location': row.click_view.location_of_presence.metro_area if hasattr(row, 'click_view') and hasattr(row.click_view, 'location_of_presence') else '',
                    'page_number': row.click_view.page_number if hasattr(row, 'click_view') and hasattr(row.click_view, 'page_number') else 0,
                    'slot': row.click_view.slot.name if hasattr(row, 'click_view') and hasattr(row.click_view, 'slot') else '',
                    'date': date_str,
                    'hour': hour,
                    'timestamp': timestamp
                }
                click_data.append(data)
        
        except GoogleAdsException as ex:
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return click_data
    
    def get_optimization_scores(
        self,
        campaign_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get optimization scores for campaigns
        
        Args:
            campaign_id: Optional campaign ID to filter (None for all campaigns)
        
        Returns:
            List of optimization score dictionaries
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
        
        optimization_data = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.optimization_score
                FROM campaign
                WHERE campaign.status != 'REMOVED'
                  {campaign_filter}
                ORDER BY campaign.optimization_score DESC
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                data = {
                    'campaign_id': str(row.campaign.id),
                    'campaign_name': row.campaign.name,
                    'optimization_score': row.campaign.optimization_score if hasattr(row.campaign, 'optimization_score') else None
                }
                optimization_data.append(data)
        
        except GoogleAdsException as ex:
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return optimization_data
    
    def get_keyword_quality_scores(
        self,
        campaign_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get quality score metrics for keywords
        
        Args:
            campaign_id: Optional campaign ID to filter
            start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
            end_date: End date in YYYY-MM-DD format (default: today)
        
        Returns:
            List of keyword quality score data
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        # Default date range: last 30 days
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
        
        campaign_filter = f"AND campaign.id = {campaign_id}" if campaign_id else ""
        
        quality_data = []
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
                    ad_group_criterion.quality_info.quality_score,
                    ad_group_criterion.quality_info.creative_quality_score,
                    ad_group_criterion.quality_info.post_click_quality_score,
                    ad_group_criterion.quality_info.search_predicted_ctr,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.ctr,
                    metrics.average_cpc,
                    metrics.conversions
                FROM keyword_view
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                  AND campaign.status != 'REMOVED'
                  {campaign_filter}
                ORDER BY ad_group_criterion.quality_info.quality_score DESC
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                quality_score = None
                creative_score = None
                landing_page_score = None
                expected_ctr = None
                
                if hasattr(row, 'ad_group_criterion') and hasattr(row.ad_group_criterion, 'quality_info'):
                    quality_info = row.ad_group_criterion.quality_info
                    quality_score = quality_info.quality_score if hasattr(quality_info, 'quality_score') else None
                    creative_score = quality_info.creative_quality_score.name if hasattr(quality_info, 'creative_quality_score') else None
                    landing_page_score = quality_info.post_click_quality_score.name if hasattr(quality_info, 'post_click_quality_score') else None
                    expected_ctr = quality_info.search_predicted_ctr.name if hasattr(quality_info, 'search_predicted_ctr') else None
                
                data = {
                    'campaign_id': str(row.campaign.id),
                    'campaign_name': row.campaign.name,
                    'ad_group_id': str(row.ad_group.id),
                    'ad_group_name': row.ad_group.name,
                    'keyword': row.ad_group_criterion.keyword.text if hasattr(row, 'ad_group_criterion') else '',
                    'match_type': row.ad_group_criterion.keyword.match_type.name if hasattr(row, 'ad_group_criterion') and hasattr(row.ad_group_criterion.keyword, 'match_type') else '',
                    'quality_score': quality_score,
                    'creative_quality_score': creative_score,
                    'landing_page_quality_score': landing_page_score,
                    'expected_ctr': expected_ctr,
                    'impressions': row.metrics.impressions if hasattr(row, 'metrics') else 0,
                    'clicks': row.metrics.clicks if hasattr(row, 'metrics') else 0,
                    'cost_micros': row.metrics.cost_micros if hasattr(row, 'metrics') else 0,
                    'ctr': row.metrics.ctr if hasattr(row, 'metrics') else 0.0,
                    'avg_cpc_micros': row.metrics.average_cpc if hasattr(row, 'metrics') else 0,
                    'conversions': row.metrics.conversions if hasattr(row, 'metrics') else 0
                }
                quality_data.append(data)
        
        except GoogleAdsException as ex:
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
            raise Exception(f"Google Ads API error ({error}): {message}")
        
        return quality_data
    
    def get_recommendations(
        self,
        campaign_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get optimization recommendations for campaigns
        
        Args:
            campaign_id: Optional campaign ID to filter (None for all campaigns)
        
        Returns:
            List of recommendation dictionaries
        """
        if not self.client:
            raise ValueError("Google Ads client not initialized")
        
        campaign_filter = f"AND recommendation.campaign.id = {campaign_id}" if campaign_id else ""
        
        recommendations = []
        try:
            ga_service = self.client.get_service("GoogleAdsService")
            # Use a simpler query with only valid fields
            query = f"""
                SELECT
                    recommendation.type,
                    recommendation.resource_name,
                    recommendation.campaign
                FROM recommendation
                WHERE recommendation.dismissed = FALSE
                  {campaign_filter}
            """
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                rec_type = row.recommendation.type.name if hasattr(row.recommendation, 'type') else 'UNKNOWN'
                
                # Get campaign ID from resource name or campaign field
                campaign_id_str = None
                if hasattr(row.recommendation, 'campaign') and row.recommendation.campaign:
                    # Campaign is a resource name like "customers/123/campaigns/456"
                    campaign_resource = str(row.recommendation.campaign)
                    if '/campaigns/' in campaign_resource:
                        campaign_id_str = campaign_resource.split('/campaigns/')[-1]
                
                # Try to get additional details from the resource name
                resource_name = row.recommendation.resource_name if hasattr(row.recommendation, 'resource_name') else ''
                
                data = {
                    'recommendation_type': rec_type,
                    'resource_name': resource_name,
                    'campaign_id': campaign_id_str,
                    'campaign_resource': str(row.recommendation.campaign) if hasattr(row.recommendation, 'campaign') and row.recommendation.campaign else None
                }
                recommendations.append(data)
        
        except GoogleAdsException as ex:
            try:
                error = ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN"
                message = ex.error.message() if hasattr(ex.error, 'message') else str(ex)
            except:
                error = "UNKNOWN"
                message = str(ex)
            # Recommendations might not be available for all accounts
            print(f"Warning: Could not fetch recommendations ({error}): {message}")
            return []
        
        return recommendations

