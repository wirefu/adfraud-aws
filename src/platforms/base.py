"""
Base classes for platform abstraction
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass


class PlatformType(Enum):
    """Supported ad platforms"""
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    LINKEDIN_ADS = "linkedin_ads"
    TWITTER_ADS = "twitter_ads"
    TIKTOK_ADS = "tiktok_ads"
    SNAPCHAT_ADS = "snapchat_ads"
    GENERIC = "generic"  # For platforms without specific adapter


@dataclass
class PlatformEvent:
    """Standardized event structure across all platforms"""
    event_id: str
    timestamp: int
    platform: PlatformType
    event_type: str  # 'click', 'impression', 'conversion', etc.
    
    # Platform-agnostic identifiers
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    ad_id: Optional[str] = None
    
    # Platform-specific identifiers (stored as dict)
    platform_specific_ids: Dict[str, Any] = None
    
    # Available signals (varies by platform)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_id: Optional[str] = None
    referrer: Optional[str] = None
    
    # Platform-specific metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.platform_specific_ids is None:
            self.platform_specific_ids = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PlatformFeatures:
    """Available features for a platform"""
    has_ip_address: bool = False
    has_user_agent: bool = False
    has_device_id: bool = False
    has_referrer: bool = False
    has_click_id: bool = False  # Platform-specific click ID (e.g., GCLID, FBCLID)
    has_keyword: bool = False
    has_targeting: bool = False
    has_placement: bool = False
    has_creative: bool = False
    
    # Platform-specific feature flags
    custom_features: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.custom_features is None:
            self.custom_features = {}


class AdPlatform(ABC):
    """Abstract base class for ad platform adapters"""
    
    @property
    @abstractmethod
    def platform_type(self) -> PlatformType:
        """Return the platform type"""
        pass
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return human-readable platform name"""
        pass
    
    @property
    @abstractmethod
    def features(self) -> PlatformFeatures:
        """Return available features for this platform"""
        pass
    
    @abstractmethod
    def parse_event(self, raw_event: Dict[str, Any]) -> PlatformEvent:
        """
        Parse raw platform event into standardized PlatformEvent
        
        Args:
            raw_event: Raw event from platform (API Gateway, webhook, etc.)
            
        Returns:
            Standardized PlatformEvent
        """
        pass
    
    @abstractmethod
    def get_context_data(
        self,
        event: PlatformEvent,
        table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get platform-specific context data for fraud detection
        
        Args:
            event: PlatformEvent to get context for
            table_name: DynamoDB table name (optional)
            
        Returns:
            Context data dictionary with platform-specific features
        """
        pass
    
    @abstractmethod
    def extract_platform_features(
        self,
        event: PlatformEvent,
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract platform-specific features for ML model
        
        Args:
            event: PlatformEvent
            context_data: Context data from get_context_data
            
        Returns:
            Dictionary of platform-specific features
        """
        pass
    
    def get_platform_identifier(self, event: PlatformEvent) -> Optional[str]:
        """
        Get platform-specific click identifier (e.g., GCLID, FBCLID)
        
        Args:
            event: PlatformEvent
            
        Returns:
            Platform-specific click ID or None
        """
        return event.platform_specific_ids.get('click_id')
    
    def is_limited_signals(self) -> bool:
        """
        Check if platform has limited signals (no IP, user agent, etc.)
        
        Returns:
            True if platform has limited signals
        """
        features = self.features
        return not (features.has_ip_address and features.has_user_agent)

