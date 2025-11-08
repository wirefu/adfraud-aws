"""
Feature Extraction for ML Model
Extracts and prepares features from ad events for XGBoost model
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List


def calculate_click_to_install_time(event: Dict[str, Any], context_data: Dict[str, Any] = None) -> float:
    """
    Calculate time between click and install events

    Args:
        event: Event dictionary
        context_data: Context data from DynamoDB

    Returns:
        Time in seconds, or 0.0 if no install found
    """
    if context_data is None:
        context_data = {}

    return event.get("click_to_install_time_sec", context_data.get("click_to_install_time_sec", 0.0))


def detect_install_broadcast_pattern(event: Dict[str, Any], context_data: Dict[str, Any] = None) -> bool:
    """
    Detect suspicious install timing patterns indicating install broadcast monitoring

    Args:
        event: Event dictionary
        context_data: Context data from DynamoDB

    Returns:
        True if install broadcast pattern detected, False otherwise
    """
    if context_data is None:
        context_data = {}

    click_to_install_time = event.get("click_to_install_time_sec", context_data.get("click_to_install_time_sec", 0.0))

    # <1 second is highly suspicious - suggests install broadcast monitoring
    return click_to_install_time > 0 and click_to_install_time < 1.0


def calculate_entropy(text: str) -> float:
    """
    Calculate Shannon entropy of a string

    Args:
        text: Input string

    Returns:
        Entropy value normalized to 0-1
    """
    if not text or len(text) == 0:
        return 0.0

    entropy = 0
    for char in set(text):
        p = text.count(char) / len(text)
        if p > 0:
            entropy -= p * math.log2(p)

    # Normalize to 0-1 (assuming max entropy is 8 bits for typical strings)
    return min(entropy / 8.0, 1.0)


def is_bot_user_agent(user_agent: str) -> bool:
    """
    Check if user agent indicates a bot

    Args:
        user_agent: User agent string

    Returns:
        True if bot, False otherwise
    """
    if not user_agent:
        return False

    bot_keywords = [
        "bot",
        "crawler",
        "spider",
        "scraper",
        "headless",
        "phantom",
        "selenium",
        "webdriver",
        "curl",
        "wget",
        "python-requests",
        "go-http-client",
        "java/",
    ]

    user_agent_lower = user_agent.lower()
    return any(keyword in user_agent_lower for keyword in bot_keywords)


def is_datacenter_ip(ip_address: str) -> bool:
    """
    Check if IP address is from a datacenter

    Args:
        ip_address: IP address string

    Returns:
        True if datacenter IP, False otherwise
    """
    if not ip_address:
        return False

    # Simplified check - in production, use IP reputation service
    # Check for private IP ranges
    parts = ip_address.split(".")
    if len(parts) != 4:
        return False

    try:
        first_octet = int(parts[0])
        second_octet = int(parts[1])

        # Private IP ranges
        if first_octet == 10:
            return True
        if first_octet == 172 and 16 <= second_octet <= 31:
            return True
        if first_octet == 192 and second_octet == 168:
            return True

        # Common datacenter ranges (simplified)
        if first_octet == 203 and second_octet == 0:
            return True

    except ValueError:
        return False

    return False


def is_vpn_ip(ip_address: str) -> bool:
    """
    Check if IP address is from a known VPN

    Args:
        ip_address: IP address string

    Returns:
        True if VPN IP, False otherwise
    """
    if not ip_address:
        return False

    # Simplified check - in production, use VPN detection service
    # Common VPN ranges (simplified)
    parts = ip_address.split(".")
    if len(parts) != 4:
        return False

    try:
        first_octet = int(parts[0])
        second_octet = int(parts[1])

        # Common VPN ranges
        if first_octet == 198 and second_octet == 51:
            return True

    except ValueError:
        return False

    return False


def is_proxy_ip(ip_address: str) -> bool:
    """
    Check if IP address is from a proxy server (beyond VPN detection)

    Args:
        ip_address: IP address string

    Returns:
        True if proxy IP, False otherwise
    """
    if not ip_address:
        return False

    # Check for VPN first (VPNs are a type of proxy)
    if is_vpn_ip(ip_address):
        return True

    # Additional proxy detection patterns
    # In production, use proxy detection service (e.g., MaxMind, IP2Location)
    parts = ip_address.split(".")
    if len(parts) != 4:
        return False

    try:
        first_octet = int(parts[0])
        second_octet = int(parts[1])

        # Common proxy ranges (simplified - would use reputation service in production)
        # Known proxy/VPN service ranges (simplified examples)
        # In production, would use comprehensive IP reputation database

        # Example proxy ranges (would be expanded with actual proxy service IPs)
        if first_octet == 45 and 65 <= second_octet <= 255:
            return True

        # Additional known proxy ranges
        if first_octet == 185 and 107 <= second_octet <= 255:
            return True

        # Common proxy service IP ranges (simplified)
        if first_octet == 104 and second_octet in [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]:
            return True

    except ValueError:
        return False

    return False


def is_business_ip(ip_address: str) -> bool:
    """
    Check if IP address is from a business/office network
    Useful for detecting competitor clicking

    Args:
        ip_address: IP address string

    Returns:
        True if business IP, False otherwise
    """
    if not ip_address:
        return False

    # In production, use IP geolocation service to check for business IPs
    # This is a simplified check - would use MaxMind or similar service
    parts = ip_address.split(".")
    if len(parts) != 4:
        return False

    try:
        first_octet = int(parts[0])
        second_octet = int(parts[1])
        third_octet = int(parts[2])

        # Common business IP patterns (simplified)
        # Office networks often use specific ranges
        # This is a placeholder - in production, use IP reputation service

        # Check for known business IP ranges (simplified)
        # Would typically use IP geolocation database

    except ValueError:
        return False

    return False


def is_competitor_ip(ip_address: str, competitor_ips: list = None) -> bool:
    """
    Check if IP address is from a known competitor

    Args:
        ip_address: IP address string
        competitor_ips: List of competitor IP ranges (optional)

    Returns:
        True if competitor IP, False otherwise
    """
    if not ip_address:
        return False

    # In production, maintain a list of competitor IP ranges
    # This would be loaded from a database or configuration
    if competitor_ips is None:
        # Default competitor IPs (would be loaded from config in production)
        competitor_ips = []

    # Check if IP matches any competitor range
    for competitor_range in competitor_ips:
        if ip_address.startswith(competitor_range):
            return True

    return False


def calculate_conversion_rate(clicks: int, conversions: int) -> float:
    """
    Calculate conversion rate from clicks to conversions

    Args:
        clicks: Number of clicks
        conversions: Number of conversions

    Returns:
        Conversion rate (0.0-1.0)
    """
    if clicks == 0:
        return 0.0
    return float(conversions) / float(clicks)


def calculate_engagement_score(click_to_view_time_ms: int, time_to_conversion_sec: float = None) -> float:
    """
    Calculate engagement score based on user interaction metrics
    Low engagement suggests incentivized clicks

    Args:
        click_to_view_time_ms: Time spent viewing after click (milliseconds)
        time_to_conversion_sec: Time to conversion in seconds (optional)

    Returns:
        Engagement score (0.0-1.0), higher is better
    """
    # Normalize view time (0-10 seconds is normal, <100ms is suspicious)
    if click_to_view_time_ms < 100:
        view_score = 0.0  # Very low engagement
    elif click_to_view_time_ms < 1000:
        view_score = 0.3  # Low engagement
    elif click_to_view_time_ms < 5000:
        view_score = 0.7  # Moderate engagement
    else:
        view_score = 1.0  # Good engagement

    # Factor in conversion time if available
    if time_to_conversion_sec is not None and time_to_conversion_sec > 0:
        # Normal conversion time: 30-300 seconds
        if time_to_conversion_sec < 10:
            conversion_score = 0.2  # Too fast, suspicious
        elif time_to_conversion_sec < 30:
            conversion_score = 0.5  # Somewhat fast
        elif time_to_conversion_sec < 300:
            conversion_score = 1.0  # Normal
        else:
            conversion_score = 0.8  # Slower but still engaged

        # Combine scores
        return (view_score * 0.6) + (conversion_score * 0.4)

    return view_score


def extract_features(event: Dict[str, Any], context_data: Dict[str, Any] = None) -> List[float]:
    """
    Extract features from event for ML model

    Args:
        event: Event dictionary with enriched data
        context_data: Additional context data from DynamoDB

    Returns:
        List of feature values in the order expected by the model
    """
    if context_data is None:
        context_data = {}
    
    # Check if this is a Google Ads event (limited signals)
    is_google_ads = event.get('source') == 'google_ads'
    
    # Get values from event or context
    ip_click_count_24h = event.get('ip_click_count_24h', context_data.get('ip_click_count_24h', 0))
    device_click_count_1h = event.get('device_click_count_1h', context_data.get('device_click_count_1h', 0))
    time_since_last_click = event.get('time_since_last_click', context_data.get('time_since_last_click', 0))
    
    # Google Ads specific features
    keyword_fraud_rate = event.get('keyword_fraud_rate', context_data.get('keyword_fraud_rate', 0.0))
    target_fraud_rate = event.get('target_fraud_rate', context_data.get('target_fraud_rate', 0.0))
    gclid_pattern_score = event.get('gclid_pattern_score', 0.5)  # Pattern analysis of GCLID
    # Temporal features
    timestamp = event.get("timestamp", int(datetime.now(timezone.utc).timestamp()))
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    hour_of_day = dt.hour
    day_of_week = dt.weekday()
    
    # User agent features (not available for Google Ads events)
    user_agent = event.get('user_agent', '') if not is_google_ads else ''
    ua_is_bot = is_bot_user_agent(user_agent) if not is_google_ads else False
    ua_entropy = calculate_entropy(user_agent) if not is_google_ads else 0.0
    
    # IP features (not available for Google Ads events)
    ip_address = event.get('ip_address', '') if not is_google_ads else ''
    ip_is_datacenter = is_datacenter_ip(ip_address) if not is_google_ads else False
    ip_is_vpn = is_vpn_ip(ip_address) if not is_google_ads else False
    ip_is_proxy = is_proxy_ip(ip_address) if not is_google_ads else False
    ip_is_business = is_business_ip(ip_address) if not is_google_ads else False

    # Competitor detection (not available for Google Ads events)
    competitor_ips = event.get("competitor_ips", context_data.get("competitor_ips", [])) if not is_google_ads else []
    ip_is_competitor = is_competitor_ip(ip_address, competitor_ips) if not is_google_ads else False
    # Geographic features (simplified - would use geo IP service in production)
    geo_distance_km = event.get("geo_distance_km", 0.0)

    # Referrer features
    referrer = event.get("referrer", "")
    referrer_is_valid = bool(referrer and referrer.startswith("http"))

    # Behavioral features
    click_to_view_time_ms = event.get("click_to_view_time_ms", 0)

    # Historical features
    campaign_fraud_rate = event.get('campaign_fraud_rate', 0.0)
    publisher_quality = event.get('publisher_quality', 0.5)
    
    # Google Ads specific historical features
    # Use keyword/target fraud rates when available (for Google Ads events)
    if is_google_ads:
        # Override campaign_fraud_rate with keyword/target rates if available
        if keyword_fraud_rate > 0:
            campaign_fraud_rate = keyword_fraud_rate
        elif target_fraud_rate > 0:
            campaign_fraud_rate = target_fraud_rate
    # Device features
    device_fingerprint_entropy = event.get("device_fingerprint_entropy", 0.5)
    is_mobile = event.get("is_mobile", False)
    is_repeated_click = event.get("is_repeated_click", False)

    # Conversion features
    time_to_conversion_sec = event.get("time_to_conversion_sec", 0.0)

    # Incentivized click detection features
    clicks_count = event.get("clicks_count", context_data.get("clicks_count", 0))
    conversions_count = event.get("conversions_count", context_data.get("conversions_count", 0))
    conversion_rate = calculate_conversion_rate(clicks_count, conversions_count)
    engagement_score = calculate_engagement_score(
        click_to_view_time_ms, time_to_conversion_sec if time_to_conversion_sec else None
    )

    # Click injection detection features
    click_to_install_time_sec = event.get("click_to_install_time_sec", context_data.get("click_to_install_time_sec", 0.0))
    has_recent_install = event.get("has_recent_install", context_data.get("has_recent_install", False))
    install_broadcast_detected = event.get("install_broadcast_detected", context_data.get("install_broadcast_detected", False))
    click_injection_risk_score = event.get("click_injection_risk_score", context_data.get("click_injection_risk_score", 0.0))

    # Categorical features (encoded)
    ip_country = event.get("ip_country", "US")
    device_os = event.get("device_os", "Windows")

    # Simple encoding for categorical features
    country_codes = ["US", "GB", "CA", "AU", "DE", "FR", "IT", "ES", "NL", "SE"]
    os_types = ["Windows", "macOS", "Linux", "iOS", "Android"]

    ip_country_encoded = country_codes.index(ip_country) if ip_country in country_codes else 0
    device_os_encoded = os_types.index(device_os) if device_os in os_types else 0

    # Return features in the order expected by the model
    # This must match the training data feature order
    # Note: Click injection features are added at the end
    # These will need to be included in model retraining
    # For Google Ads events, use pattern-based features when browser signals unavailable
    features = [
        float(ip_click_count_24h),
        float(device_click_count_1h),
        float(time_since_last_click) if time_since_last_click else 0.0,
        float(hour_of_day),
        float(day_of_week),
        float(1 if ua_is_bot else 0),
        float(ua_entropy),
        float(1 if ip_is_datacenter else 0),
        float(1 if ip_is_vpn else 0),
        float(1 if ip_is_proxy else 0),
        float(1 if ip_is_business else 0),
        float(1 if ip_is_competitor else 0),
        float(geo_distance_km),
        float(1 if referrer_is_valid else 0),
        float(click_to_view_time_ms),
        float(campaign_fraud_rate),
        float(publisher_quality),
        float(device_fingerprint_entropy),
        float(1 if is_mobile else 0),
        float(1 if is_repeated_click else 0),
        float(time_to_conversion_sec) if time_to_conversion_sec else 0.0,
        float(ip_country_encoded),
        float(device_os_encoded),
        # Click injection features (new - will need model retraining)
        float(click_to_install_time_sec),
        float(1 if has_recent_install else 0),
        float(1 if install_broadcast_detected else 0),
        float(click_injection_risk_score),
        # Incentivized click detection features (new - will need model retraining)
        float(conversion_rate),
        float(engagement_score),
        # Competitor clicking detection features (new - will need model retraining)
        # Note: ip_is_competitor and ip_is_business already included above
    ]
    
    # For Google Ads events, add Google-specific features if model supports them
    # Note: Model may need retraining to include these features
    if is_google_ads:
        # Add Google-specific features (may need model update)
        features.extend([
            float(keyword_fraud_rate),
            float(target_fraud_rate),
            float(gclid_pattern_score),
        ])
    
    return features
