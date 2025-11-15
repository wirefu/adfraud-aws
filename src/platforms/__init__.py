"""
Multi-Platform Ad Fraud Detection Support

This module provides platform abstraction for multiple ad platforms:
- Google Ads
- Meta Ads (Facebook/Instagram)
- LinkedIn Ads
- Other social media platforms
"""

from .base import AdPlatform, PlatformEvent, PlatformFeatures
from .google_ads import GoogleAdsPlatform
from .meta_ads import MetaAdsPlatform
from .linkedin_ads import LinkedInAdsPlatform
from .factory import get_platform_adapter

__all__ = [
    'AdPlatform',
    'PlatformEvent',
    'PlatformFeatures',
    'GoogleAdsPlatform',
    'MetaAdsPlatform',
    'LinkedInAdsPlatform',
    'get_platform_adapter',
]

