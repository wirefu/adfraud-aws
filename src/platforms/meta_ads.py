"""
Meta Ads (Facebook/Instagram) Platform Adapter
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from .base import AdPlatform, PlatformType, PlatformEvent, PlatformFeatures


class MetaAdsPlatform(AdPlatform):
    """Meta Ads platform adapter"""
    
    @property
    def platform_type(self) -> PlatformType:
        return PlatformType.META_ADS
    
    @property
    def platform_name(self) -> str:
        return "Meta Ads"
    
    @property
    def features(self) -> PlatformFeatures:
        """Meta Ads has click ID and some targeting data"""
        return PlatformFeatures(
            has_ip_address=False,  # Not available in server-side events
            has_user_agent=False,  # Not available in server-side events
            has_device_id=False,   # Not available in server-side events
            has_referrer=False,    # Not available in server-side events
            has_click_id=True,     # FBCLID available
            has_keyword=False,     # No keywords in Meta Ads
            has_targeting=True,    # Audience targeting available
            has_placement=True,   # Placement available (Facebook, Instagram, etc.)
            has_creative=True,    # Creative ID available
            custom_features={
                'has_fbclid': True,
                'has_campaign_id': True,
                'has_ad_set_id': True,
                'has_audience': True,
            }
        )
    
    def parse_event(self, raw_event: Dict[str, Any]) -> PlatformEvent:
        """
        Parse Meta Ads server-side event
        
        Expected format (Meta Conversions API):
        {
            'event_id': '...',
            'event_time': 1234567890,
            'event_name': 'Click',
            'action_source': 'website',
            'fbclid': '...',
            'campaign_id': '...',
            'adset_id': '...',
            'ad_id': '...',
            'user_data': {...},
            'custom_data': {...},
        }
        """
        # Extract timestamp
        if 'event_time' in raw_event:
            timestamp = raw_event['event_time']
        elif 'timestamp' in raw_event:
            timestamp = raw_event['timestamp']
        else:
            timestamp = int(datetime.now(timezone.utc).timestamp())
        
        # Extract event ID
        event_id = raw_event.get('event_id')
        if not event_id:
            from uuid import uuid4
            event_id = str(uuid4())
        
        # Extract platform-specific IDs
        platform_ids = {
            'click_id': raw_event.get('fbclid', ''),
            'campaign_id': raw_event.get('campaign_id', ''),
            'ad_set_id': raw_event.get('adset_id', ''),
            'ad_id': raw_event.get('ad_id', ''),
            'placement': raw_event.get('placement', ''),
        }
        
        # Extract metadata
        metadata = {
            'event_name': raw_event.get('event_name', 'Click'),
            'action_source': raw_event.get('action_source', 'website'),
            'original_source': 'meta_ads',
        }
        
        return PlatformEvent(
            event_id=event_id,
            timestamp=timestamp,
            platform=PlatformType.META_ADS,
            event_type=raw_event.get('event_name', 'click').lower(),
            campaign_id=raw_event.get('campaign_id', ''),
            ad_group_id=raw_event.get('adset_id', ''),  # Map adset to ad_group
            ad_id=raw_event.get('ad_id', ''),
            platform_specific_ids=platform_ids,
            metadata=metadata
        )
    
    def get_context_data(
        self,
        event: PlatformEvent,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Meta Ads context data"""
        if not table_name:
            import os
            table_name = os.environ.get('DYNAMODB_TABLE_NAME')
        
        if not table_name:
            return {}
        
        context = {}
        
        # Get campaign fraud rate (would need to implement)
        campaign_id = event.campaign_id
        if campaign_id:
            # TODO: Implement get_campaign_fraud_rate for Meta Ads
            context['campaign_fraud_rate'] = 0.0
        
        # Get placement fraud rate
        placement = event.platform_specific_ids.get('placement')
        if placement:
            # TODO: Implement get_placement_fraud_rate for Meta Ads
            context['placement_fraud_rate'] = 0.0
        
        # Analyze FBCLID pattern
        fbclid = event.platform_specific_ids.get('click_id')
        if fbclid:
            context['fbclid_pattern_score'] = self._analyze_fbclid_pattern(fbclid)
        else:
            context['fbclid_pattern_score'] = 0.5
        
        return context
    
    def extract_platform_features(
        self,
        event: PlatformEvent,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract Meta Ads specific features"""
        features = {}
        
        # Placement fraud rate
        features['placement_fraud_rate'] = context_data.get('placement_fraud_rate', 0.0)
        features['fbclid_pattern_score'] = context_data.get('fbclid_pattern_score', 0.5)
        features['campaign_fraud_rate'] = context_data.get('campaign_fraud_rate', 0.0)
        
        # Meta-specific features
        placement = event.platform_specific_ids.get('placement', '')
        features['is_facebook_placement'] = 1.0 if 'facebook' in placement.lower() else 0.0
        features['is_instagram_placement'] = 1.0 if 'instagram' in placement.lower() else 0.0
        
        return features
    
    def _analyze_fbclid_pattern(self, fbclid: str) -> float:
        """Analyze FBCLID pattern for fraud indicators"""
        if not fbclid:
            return 0.5
        
        # Similar pattern analysis as GCLID
        if len(fbclid) < 20:
            return 0.3
        
        if len(set(fbclid)) < len(fbclid) * 0.3:
            return 0.4
        
        return 0.7

