"""
Platform factory for creating platform adapters
"""
from typing import Optional, Dict, Any
from .base import AdPlatform, PlatformType
from .google_ads import GoogleAdsPlatform
from .meta_ads import MetaAdsPlatform
from .linkedin_ads import LinkedInAdsPlatform


# Registry of platform adapters
_PLATFORM_REGISTRY: Dict[PlatformType, type] = {
    PlatformType.GOOGLE_ADS: GoogleAdsPlatform,
    PlatformType.META_ADS: MetaAdsPlatform,
    PlatformType.LINKEDIN_ADS: LinkedInAdsPlatform,
}


def get_platform_adapter(
    platform: PlatformType,
    source: Optional[str] = None
) -> AdPlatform:
    """
    Get platform adapter for a given platform type
    
    Args:
        platform: PlatformType enum
        source: Optional source string (for backward compatibility)
        
    Returns:
        AdPlatform instance
    """
    # Handle backward compatibility with source string
    if source:
        source_to_platform = {
            'google_ads': PlatformType.GOOGLE_ADS,
            'meta_ads': PlatformType.META_ADS,
            'linkedin_ads': PlatformType.LINKEDIN_ADS,
        }
        if source in source_to_platform:
            platform = source_to_platform[source]
    
    # Get adapter class from registry
    adapter_class = _PLATFORM_REGISTRY.get(platform)
    if not adapter_class:
        raise ValueError(f"No adapter available for platform: {platform}")
    
    # Return new instance
    return adapter_class()


def detect_platform_from_event(event: Dict[str, Any]) -> PlatformType:
    """
    Detect platform type from raw event
    
    Args:
        event: Raw event dictionary
        
    Returns:
        PlatformType enum
    """
    # Check for explicit platform field
    if 'platform' in event:
        try:
            return PlatformType(event['platform'])
        except ValueError:
            pass
    
    # Check for source field (backward compatibility)
    source = event.get('source', '').lower()
    source_to_platform = {
        'google_ads': PlatformType.GOOGLE_ADS,
        'meta_ads': PlatformType.META_ADS,
        'linkedin_ads': PlatformType.LINKEDIN_ADS,
    }
    if source in source_to_platform:
        return source_to_platform[source]
    
    # Check for platform-specific identifiers
    if 'gclid' in event or 'cid' in event:
        return PlatformType.GOOGLE_ADS
    
    if 'fbclid' in event or 'campaign_id' in event and 'adset_id' in event:
        return PlatformType.META_ADS
    
    if 'click_id' in event and 'audience_id' in event:
        return PlatformType.LINKEDIN_ADS
    
    # Default to generic
    return PlatformType.GENERIC

