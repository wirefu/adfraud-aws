"""
Google Ads Platform Adapter
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from .base import AdPlatform, PlatformType, PlatformEvent, PlatformFeatures
from ..storage.dynamodb_utils import (
    get_keyword_fraud_rate,
    get_target_fraud_rate
)


class GoogleAdsPlatform(AdPlatform):
    """Google Ads platform adapter"""
    
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.GOOGLE_ADS
    
    @property
    def platform_name(self) -> str:
        return "Google Ads"
    
    @property
    def features(self) -> PlatformFeatures:
        """Google Ads has limited signals (parallel tracking)"""
        return PlatformFeatures(
            has_ip_address=False,  # Not available in parallel tracking
            has_user_agent=False,  # Not available in parallel tracking
            has_device_id=False,  # Not available in parallel tracking
            has_referrer=False,    # Not available in parallel tracking
            has_click_id=True,     # GCLID available
            has_keyword=True,      # Keyword available
            has_targeting=True,    # Target/placement ID available
            has_placement=True,   # Placement available
            has_creative=True,     # Creative ID available
            custom_features={
                'has_gclid': True,
                'has_campaign_id': True,
                'has_ad_group_id': True,
            }
        )
    
    def parse_event(self, raw_event: Dict[str, Any]) -> PlatformEvent:
        """
        Parse Google Ads parallel tracking event
        
        Expected format:
        {
            'gclid': '...',
            'cid': 'campaign_id',
            'aid': 'ad_group_id',
            'kw': 'keyword',
            'target': 'target_id',
            'creative': 'creative_id',
            'mt': 'match_type',
            'device': 'device_type',
            ...
        }
        """
        # Extract timestamp
        if 'timestamp' in raw_event:
            timestamp = raw_event['timestamp']
        elif 'created_at' in raw_event:
            # Parse ISO format
            dt = datetime.fromisoformat(raw_event['created_at'].replace('Z', '+00:00'))
            timestamp = int(dt.timestamp())
        else:
            timestamp = int(datetime.now(timezone.utc).timestamp())
        
        # Extract event ID
        event_id = raw_event.get('event_id')
        if not event_id:
            from uuid import uuid4
            event_id = str(uuid4())
        
        # Extract platform-specific IDs
        platform_ids = {
            'click_id': raw_event.get('gclid', ''),
            'campaign_id': raw_event.get('cid', ''),
            'ad_group_id': raw_event.get('aid', ''),
            'keyword': raw_event.get('kw', ''),
            'target_id': raw_event.get('target', ''),
            'creative_id': raw_event.get('creative', ''),
            'match_type': raw_event.get('mt', ''),
        }
        
        # Extract metadata
        metadata = {
            'device': raw_event.get('device', ''),
            'match_type': raw_event.get('mt', ''),
            'original_source': 'google_ads',
        }
        
        return PlatformEvent(
            event_id=event_id,
            timestamp=timestamp,
            platform=PlatformType.GOOGLE_ADS,
            event_type='click',
            campaign_id=raw_event.get('cid', ''),
            ad_group_id=raw_event.get('aid', ''),
            platform_specific_ids=platform_ids,
            metadata=metadata
        )
    
    def get_context_data(
        self,
        event: PlatformEvent,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Google Ads context data (keyword/target fraud rates)"""
        if not table_name:
            import os
            table_name = os.environ.get('DYNAMODB_TABLE_NAME')
        
        if not table_name:
            return {}
        
        context = {}
        
        # Get keyword fraud rate
        keyword = event.platform_specific_ids.get('keyword')
        if keyword:
            try:
                keyword_fraud_rate = get_keyword_fraud_rate(table_name, keyword, days=30)
                context['keyword_fraud_rate'] = keyword_fraud_rate
            except Exception as e:
                print(f"Error getting keyword fraud rate: {e}")
                context['keyword_fraud_rate'] = 0.0
        
        # Get target fraud rate
        target_id = event.platform_specific_ids.get('target_id')
        if target_id:
            try:
                target_fraud_rate = get_target_fraud_rate(table_name, target_id, days=30)
                context['target_fraud_rate'] = target_fraud_rate
            except Exception as e:
                print(f"Error getting target fraud rate: {e}")
                context['target_fraud_rate'] = 0.0
        
        # Analyze GCLID pattern
        gclid = event.platform_specific_ids.get('click_id')
        if gclid:
            context['gclid_pattern_score'] = self._analyze_gclid_pattern(gclid)
        else:
            context['gclid_pattern_score'] = 0.5
        
        return context
    
    def extract_platform_features(
        self,
        event: PlatformEvent,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract Google Ads specific features"""
        features = {}
        
        # Keyword and target fraud rates
        features['keyword_fraud_rate'] = context_data.get('keyword_fraud_rate', 0.0)
        features['target_fraud_rate'] = context_data.get('target_fraud_rate', 0.0)
        features['gclid_pattern_score'] = context_data.get('gclid_pattern_score', 0.5)
        
        # Use keyword/target fraud rate as campaign fraud rate
        if features['keyword_fraud_rate'] > 0:
            features['campaign_fraud_rate'] = features['keyword_fraud_rate']
        elif features['target_fraud_rate'] > 0:
            features['campaign_fraud_rate'] = features['target_fraud_rate']
        else:
            features['campaign_fraud_rate'] = 0.0
        
        return features
    
    def _analyze_gclid_pattern(self, gclid: str) -> float:
        """
        Analyze GCLID pattern for fraud indicators
        
        Returns:
            Score between 0.0 (suspicious) and 1.0 (normal)
        """
        if not gclid:
            return 0.5
        
        # Simple pattern analysis (can be enhanced)
        # Check for suspicious patterns
        if len(gclid) < 20:
            return 0.3  # Suspiciously short
        
        # Check for repeated characters (potential bot generation)
        if len(set(gclid)) < len(gclid) * 0.3:
            return 0.4  # Too many repeated characters
        
        # Normal GCLID
        return 0.7

