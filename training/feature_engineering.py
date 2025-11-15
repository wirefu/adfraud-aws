"""
Feature Engineering Module for Training Data

Converts raw data (TalkingData, Google Ads) into features matching
the production feature extractor (src/orchestrator/feature_extractor.py)

Feature Order (29 base features + 3 Google Ads optional):
1. ip_click_count_24h
2. device_click_count_1h
3. time_since_last_click
4. hour_of_day
5. day_of_week
6. ua_is_bot
7. ua_entropy
8. ip_is_datacenter
9. ip_is_vpn
10. ip_is_proxy
11. ip_is_business
12. ip_is_competitor
13. geo_distance_km
14. referrer_is_valid
15. click_to_view_time_ms
16. campaign_fraud_rate
17. publisher_quality
18. device_fingerprint_entropy
19. is_mobile
20. is_repeated_click
21. time_to_conversion_sec
22. ip_country_encoded
23. device_os_encoded
24. click_to_install_time_sec
25. has_recent_install
26. install_broadcast_detected
27. click_injection_risk_score
28. conversion_rate
29. engagement_score
30. keyword_fraud_rate (Google Ads only)
31. target_fraud_rate (Google Ads only)
32. gclid_pattern_score (Google Ads only)
"""

import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import helper functions from production feature extractor
try:
    from src.orchestrator.feature_extractor import (
        calculate_entropy,
        is_bot_user_agent,
        is_datacenter_ip,
        is_vpn_ip,
        is_proxy_ip,
        is_business_ip,
        is_competitor_ip,
        calculate_conversion_rate,
        calculate_engagement_score,
    )
except ImportError:
    # Fallback implementations if import fails
    def calculate_entropy(text: str) -> float:
        if not text or len(text) == 0:
            return 0.0
        entropy = 0
        for char in set(text):
            p = text.count(char) / len(text)
            if p > 0:
                entropy -= p * math.log2(p)
        return min(entropy / 8.0, 1.0)
    
    def is_bot_user_agent(user_agent: str) -> bool:
        if not user_agent:
            return False
        bot_keywords = ["bot", "crawler", "spider", "scraper", "headless", "phantom", "selenium", "webdriver"]
        return any(keyword in user_agent.lower() for keyword in bot_keywords)
    
    def is_datacenter_ip(ip_address: str) -> bool:
        if not ip_address:
            return False
        parts = ip_address.split(".")
        if len(parts) != 4:
            return False
        try:
            first = int(parts[0])
            second = int(parts[1])
            return (first == 10) or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)
        except:
            return False
    
    def is_vpn_ip(ip_address: str) -> bool:
        return False  # Simplified
    
    def is_proxy_ip(ip_address: str) -> bool:
        return is_vpn_ip(ip_address)  # Simplified
    
    def is_business_ip(ip_address: str) -> bool:
        return False  # Simplified
    
    def is_competitor_ip(ip_address: str, competitor_ips: list = None) -> bool:
        return False  # Simplified
    
    def calculate_conversion_rate(clicks: int, conversions: int) -> float:
        return float(conversions) / float(clicks) if clicks > 0 else 0.0
    
    def calculate_engagement_score(click_to_view_time_ms: int, time_to_conversion_sec: float = None) -> float:
        if click_to_view_time_ms < 100:
            return 0.0
        elif click_to_view_time_ms < 1000:
            return 0.3
        elif click_to_view_time_ms < 5000:
            return 0.7
        else:
            return 1.0


# Feature order matching production extractor
FEATURE_NAMES = [
    'ip_click_count_24h',
    'device_click_count_1h',
    'time_since_last_click',
    'hour_of_day',
    'day_of_week',
    'ua_is_bot',
    'ua_entropy',
    'ip_is_datacenter',
    'ip_is_vpn',
    'ip_is_proxy',
    'ip_is_business',
    'ip_is_competitor',
    'geo_distance_km',
    'referrer_is_valid',
    'click_to_view_time_ms',
    'campaign_fraud_rate',
    'publisher_quality',
    'device_fingerprint_entropy',
    'is_mobile',
    'is_repeated_click',
    'time_to_conversion_sec',
    'ip_country_encoded',
    'device_os_encoded',
    'click_to_install_time_sec',
    'has_recent_install',
    'install_broadcast_detected',
    'click_injection_risk_score',
    'conversion_rate',
    'engagement_score',
]

# Google Ads additional features
GOOGLE_ADS_FEATURES = [
    'keyword_fraud_rate',
    'target_fraud_rate',
    'gclid_pattern_score',
]

# Categorical encodings (must match production extractor)
COUNTRY_CODES = ["US", "GB", "CA", "AU", "DE", "FR", "IT", "ES", "NL", "SE"]
OS_TYPES = ["Windows", "macOS", "Linux", "iOS", "Android"]


def convert_integer_ip_to_string(ip_int: int) -> str:
    """
    Convert integer-encoded IP to string format
    
    Args:
        ip_int: Integer representation of IP
    
    Returns:
        IP address string (e.g., "192.168.1.1")
    """
    if pd.isna(ip_int) or ip_int == 0:
        return ""
    
    # Convert integer to IP string
    # IP is stored as integer: a.b.c.d = a*256^3 + b*256^2 + c*256 + d
    octet1 = (ip_int >> 24) & 0xFF
    octet2 = (ip_int >> 16) & 0xFF
    octet3 = (ip_int >> 8) & 0xFF
    octet4 = ip_int & 0xFF
    
    return f"{octet1}.{octet2}.{octet3}.{octet4}"


def compute_aggregated_features(df: pd.DataFrame, use_chunking: bool = False, chunk_size: int = 100000) -> pd.DataFrame:
    """
    Compute aggregated features (IP click counts, device click counts, time since last click)
    Uses optimized vectorized operations for efficiency
    
    Args:
        df: DataFrame with ip, device, click_time columns
        use_chunking: If True, process in chunks for very large datasets
        chunk_size: Size of chunks when use_chunking=True
    
    Returns:
        DataFrame with aggregated features added
    """
    df = df.copy()
    
    # Ensure click_time is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['click_time']):
        df['click_time'] = pd.to_datetime(df['click_time'])
    
    # Store original index for restoration
    original_index = df.index.copy()
    
    # Sort by click_time for proper aggregation
    df = df.sort_values('click_time').reset_index(drop=True)
    
    print(f"Computing aggregated features for {len(df):,} rows...")
    
    # Use chunking for very large datasets
    if use_chunking and len(df) > chunk_size:
        print(f"  Using chunked processing (chunk_size={chunk_size:,})...")
        return _compute_aggregated_features_chunked(df, chunk_size)
    
    # Optimized vectorized approach for smaller datasets
    print("  Computing IP click counts (24h window)...")
    
    # For IP click counts: use merge_asof for efficient time-based window joins
    # Group by IP and use expanding window with time constraint
    df['ip_click_count_24h'] = 0
    df['device_click_count_1h'] = 0
    df['time_since_last_click'] = 0.0
    
    # Process by IP groups for 24h window
    ip_groups = df.groupby('ip', sort=False)
    ip_results = []
    
    for ip, ip_group in ip_groups:
        ip_group = ip_group.sort_values('click_time').reset_index(drop=True)
        
        # Ensure click_time is datetime
        if not pd.api.types.is_datetime64_any_dtype(ip_group['click_time']):
            ip_group['click_time'] = pd.to_datetime(ip_group['click_time'])
        
        # Use vectorized approach: for each row, count previous rows within 24h
        click_times = pd.to_datetime(ip_group['click_time']).values
        ip_counts = []
        
        for i in range(len(ip_group)):
            # Count previous clicks within 24h window
            current_time = pd.Timestamp(click_times[i])
            window_start = current_time - timedelta(hours=24)
            window_start_ts = pd.Timestamp(window_start)
            
            # Convert to timestamps for comparison
            prev_times = [pd.Timestamp(click_times[j]) for j in range(i)]
            count = sum(1 for t in prev_times if window_start_ts <= t < current_time)
            ip_counts.append(count)
        
        ip_group['ip_click_count_24h'] = ip_counts
        ip_results.append(ip_group)
    
    if ip_results:
        df = pd.concat(ip_results, ignore_index=True)
    
    print("  Computing device click counts (1h window) and time since last click...")
    
    # Process by device groups for 1h window and time since last click
    device_groups = df.groupby('device', sort=False)
    device_results = []
    
    for device, device_group in device_groups:
        device_group = device_group.sort_values('click_time').reset_index(drop=True)
        
        # Ensure click_time is datetime
        if not pd.api.types.is_datetime64_any_dtype(device_group['click_time']):
            device_group['click_time'] = pd.to_datetime(device_group['click_time'])
        
        click_times = pd.to_datetime(device_group['click_time']).values
        device_counts = []
        time_since_last = []
        
        for i in range(len(device_group)):
            # Count previous clicks within 1h window
            current_time = pd.Timestamp(click_times[i])
            window_start = current_time - timedelta(hours=1)
            window_start_ts = pd.Timestamp(window_start)
            
            # Convert to timestamps for comparison
            prev_times = [pd.Timestamp(click_times[j]) for j in range(i)]
            count = sum(1 for t in prev_times if window_start_ts <= t < current_time)
            device_counts.append(count)
            
            # Time since last click
            if i > 0:
                prev_time = pd.Timestamp(click_times[i-1])
                time_diff = (current_time - prev_time).total_seconds()
                time_since_last.append(time_diff)
            else:
                time_since_last.append(0.0)
        
        device_group['device_click_count_1h'] = device_counts
        device_group['time_since_last_click'] = time_since_last
        device_results.append(device_group)
    
    if device_results:
        df = pd.concat(device_results, ignore_index=True)
    
    # Restore original index order if possible
    if len(df) == len(original_index):
        df.index = original_index
    
    return df


def _compute_aggregated_features_chunked(df: pd.DataFrame, chunk_size: int) -> pd.DataFrame:
    """
    Compute aggregated features using chunked processing for very large datasets
    
    Args:
        df: DataFrame sorted by click_time
        chunk_size: Size of each chunk
    
    Returns:
        DataFrame with aggregated features
    """
    print(f"  Processing in chunks of {chunk_size:,} rows...")
    
    all_results = []
    num_chunks = (len(df) + chunk_size - 1) // chunk_size
    
    for chunk_idx in range(num_chunks):
        start_idx = chunk_idx * chunk_size
        end_idx = min((chunk_idx + 1) * chunk_size, len(df))
        
        print(f"    Processing chunk {chunk_idx + 1}/{num_chunks} (rows {start_idx:,}-{end_idx:,})...")
        
        # Get chunk with overlap for proper window calculations
        # Need to look back 24h for IP counts, 1h for device counts
        chunk_start_time = df.iloc[start_idx]['click_time'] - timedelta(hours=24)
        chunk_start_idx = df[df['click_time'] >= chunk_start_time].index[0] if len(df[df['click_time'] >= chunk_start_time]) > 0 else start_idx
        
        chunk_df = df.iloc[chunk_start_idx:end_idx].copy()
        
        # Compute features for this chunk
        chunk_df = compute_aggregated_features(chunk_df, use_chunking=False)
        
        # Only keep the original chunk range (not the overlap)
        chunk_df = chunk_df.iloc[start_idx - chunk_start_idx:].copy()
        
        all_results.append(chunk_df)
    
    result_df = pd.concat(all_results, ignore_index=True)
    return result_df


def engineer_talkingdata_features(df: pd.DataFrame, use_chunking: bool = False, preprocess: bool = False) -> pd.DataFrame:
    """
    Engineer features from TalkingData format
    
    Args:
        df: DataFrame with TalkingData columns (ip, app, device, os, channel, click_time, is_attributed)
        use_chunking: If True, process in chunks for large datasets
        preprocess: If True, apply preprocessing (missing values, encoding). Default False to avoid duplicate processing
    
    Returns:
        DataFrame with engineered features matching production extractor
    """
    print("Engineering features from TalkingData format...")
    df = df.copy()
    
    # Convert label: is_attributed=0 means fraud, is_attributed=1 means legitimate
    if 'is_attributed' in df.columns:
        df['is_fraud'] = 1 - df['is_attributed']
    
    # Ensure click_time is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['click_time']):
        df['click_time'] = pd.to_datetime(df['click_time'])
    
    # Compute aggregated features (with chunking support for large datasets)
    chunk_size = 100000 if use_chunking else None
    df = compute_aggregated_features(df, use_chunking=use_chunking, chunk_size=chunk_size if chunk_size else 100000)
    
    # Temporal features
    df['hour_of_day'] = df['click_time'].dt.hour
    df['day_of_week'] = df['click_time'].dt.dayofweek
    
    # Convert integer IP to string for reputation checks
    df['ip_address'] = df['ip'].apply(convert_integer_ip_to_string)
    
    # User agent features (not available in TalkingData - set defaults)
    df['ua_is_bot'] = False
    df['ua_entropy'] = 0.0
    
    # IP reputation features
    df['ip_is_datacenter'] = df['ip_address'].apply(is_datacenter_ip)
    df['ip_is_vpn'] = df['ip_address'].apply(is_vpn_ip)
    df['ip_is_proxy'] = df['ip_address'].apply(is_proxy_ip)
    df['ip_is_business'] = df['ip_address'].apply(is_business_ip)
    df['ip_is_competitor'] = df['ip_address'].apply(lambda ip: is_competitor_ip(ip, []))
    
    # Geographic features (not available - set defaults)
    df['geo_distance_km'] = 0.0
    df['ip_country'] = 'US'  # Default
    df['ip_country_encoded'] = df['ip_country'].apply(
        lambda c: COUNTRY_CODES.index(c) if c in COUNTRY_CODES else 0
    )
    
    # Referrer features (not available - set defaults)
    df['referrer_is_valid'] = False
    
    # Behavioral features (not available - set defaults)
    df['click_to_view_time_ms'] = 0
    
    # Historical features (use app/channel as proxies)
    # App can represent campaign, channel can represent publisher
    df['campaign_fraud_rate'] = 0.0  # Would need historical data
    df['publisher_quality'] = 0.5  # Default
    
    # Device features
    # Use device ID entropy as device fingerprint entropy
    device_counts = df['device'].value_counts()
    df['device_fingerprint_entropy'] = df['device'].apply(
        lambda d: calculate_entropy(str(d)) if d in device_counts.index else 0.5
    )
    
    # OS-based mobile detection (simplified)
    # In TalkingData, os is an integer - assume lower values might be mobile
    df['is_mobile'] = df['os'].apply(lambda x: 1 if x < 10 else 0)  # Simplified heuristic
    
    # Repeated click detection
    df['is_repeated_click'] = df.duplicated(subset=['ip', 'device', 'app'], keep='first')
    
    # Conversion features
    # Time to conversion = time between click and attribution
    if 'attributed_time' in df.columns:
        df['time_to_conversion_sec'] = (
            (df['attributed_time'] - df['click_time']).dt.total_seconds()
        ).fillna(0.0)
    else:
        df['time_to_conversion_sec'] = 0.0
    
    # Device OS encoding (use os integer as encoded value, simplified)
    df['device_os_encoded'] = df['os'].apply(lambda x: min(x % len(OS_TYPES), len(OS_TYPES) - 1))
    
    # Click injection features
    df['click_to_install_time_sec'] = df['time_to_conversion_sec']  # Same as conversion time
    df['has_recent_install'] = df['is_attributed'] == 1 if 'is_attributed' in df.columns else False
    df['install_broadcast_detected'] = (
        (df['click_to_install_time_sec'] > 0) & 
        (df['click_to_install_time_sec'] < 1.0)
    )
    df['click_injection_risk_score'] = df.apply(
        lambda row: 0.8 if row['install_broadcast_detected'] else 0.0, axis=1
    )
    
    # Engagement features
    df['conversion_rate'] = df.apply(
        lambda row: 1.0 if row.get('is_attributed', 0) == 1 else 0.0, axis=1
    )
    df['engagement_score'] = df['click_to_view_time_ms'].apply(
        lambda x: calculate_engagement_score(int(x))
    )
    
    # Select and order features to match production extractor
    feature_columns = FEATURE_NAMES.copy()
    
    # Check which features exist
    available_features = [f for f in feature_columns if f in df.columns]
    missing_features = [f for f in feature_columns if f not in df.columns]
    
    if missing_features:
        print(f"  Warning: Missing features (will use defaults): {missing_features}")
        for feat in missing_features:
            df[feat] = 0.0  # Default value
    
    # Ensure correct order and convert to float
    feature_df = df[FEATURE_NAMES].copy()
    for col in feature_df.columns:
        feature_df[col] = feature_df[col].astype(float)
    
    # Handle missing values if requested (usually done in integration function)
    if preprocess:
        from training.preprocessing import handle_missing_values
        feature_df = handle_missing_values(feature_df, strategy="auto")
    
    # Add label if available
    if 'is_fraud' in df.columns:
        feature_df['is_fraud'] = df['is_fraud']
    elif 'is_attributed' in df.columns:
        feature_df['is_fraud'] = 1 - df['is_attributed']
    
    return feature_df


def engineer_google_ads_features(df: pd.DataFrame, preprocess: bool = False) -> pd.DataFrame:
    """
    Engineer features from Google Ads format (from DynamoDB)
    
    Args:
        df: DataFrame with Google Ads event columns
        preprocess: If True, apply preprocessing (missing values, encoding). Default False to avoid duplicate processing
    
    Returns:
        DataFrame with engineered features matching production extractor
    """
    print("Engineering features from Google Ads format...")
    df = df.copy()
    
    # Ensure timestamp is datetime
    if 'timestamp' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df['click_time'] = df['timestamp']
    elif 'click_time' not in df.columns:
        df['click_time'] = pd.Timestamp.now()
    
    # Compute aggregated features (if not already computed)
    if 'ip_click_count_24h' not in df.columns:
        df = compute_aggregated_features(df)
    
    # Temporal features
    if 'timestamp' in df.columns:
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
    else:
        df['hour_of_day'] = 0
        df['day_of_week'] = 0
    
    # User agent features (if available)
    if 'user_agent' in df.columns:
        df['ua_is_bot'] = df['user_agent'].apply(is_bot_user_agent)
        df['ua_entropy'] = df['user_agent'].apply(calculate_entropy)
    else:
        df['ua_is_bot'] = False
        df['ua_entropy'] = 0.0
    
    # IP reputation features
    if 'ip_address' in df.columns:
        df['ip_is_datacenter'] = df['ip_address'].apply(is_datacenter_ip)
        df['ip_is_vpn'] = df['ip_address'].apply(is_vpn_ip)
        df['ip_is_proxy'] = df['ip_address'].apply(is_proxy_ip)
        df['ip_is_business'] = df['ip_address'].apply(is_business_ip)
        df['ip_is_competitor'] = df['ip_address'].apply(lambda ip: is_competitor_ip(ip, []))
    else:
        for feat in ['ip_is_datacenter', 'ip_is_vpn', 'ip_is_proxy', 'ip_is_business', 'ip_is_competitor']:
            df[feat] = False
    
    # Geographic features
    df['geo_distance_km'] = df.get('geo_distance_km', 0.0)
    if 'ip_country' in df.columns:
        df['ip_country_encoded'] = df['ip_country'].apply(
            lambda c: COUNTRY_CODES.index(c) if c in COUNTRY_CODES else 0
        )
    else:
        df['ip_country'] = 'US'
        df['ip_country_encoded'] = 0
    
    # Referrer features
    if 'referrer' in df.columns:
        df['referrer_is_valid'] = df['referrer'].apply(lambda x: bool(x and str(x).startswith('http')))
    else:
        df['referrer_is_valid'] = False
    
    # Behavioral features
    df['click_to_view_time_ms'] = df.get('click_to_view_time_ms', 0)
    
    # Historical features
    df['campaign_fraud_rate'] = df.get('campaign_fraud_rate', 0.0)
    df['publisher_quality'] = df.get('publisher_quality', 0.5)
    
    # Device features
    df['device_fingerprint_entropy'] = df.get('device_fingerprint_entropy', 0.5)
    df['is_mobile'] = df.get('is_mobile', False)
    df['is_repeated_click'] = df.get('is_repeated_click', False)
    
    # Conversion features
    df['time_to_conversion_sec'] = df.get('time_to_conversion_sec', 0.0)
    
    # Device OS encoding
    if 'device_os' in df.columns:
        df['device_os_encoded'] = df['device_os'].apply(
            lambda os: OS_TYPES.index(os) if os in OS_TYPES else 0
        )
    else:
        df['device_os_encoded'] = 0
    
    # Click injection features
    df['click_to_install_time_sec'] = df.get('click_to_install_time_sec', 0.0)
    df['has_recent_install'] = df.get('has_recent_install', False)
    df['install_broadcast_detected'] = df.get('install_broadcast_detected', False)
    df['click_injection_risk_score'] = df.get('click_injection_risk_score', 0.0)
    
    # Engagement features
    if 'clicks' in df.columns and 'conversions' in df.columns:
        df['conversion_rate'] = df.apply(
            lambda row: calculate_conversion_rate(
                int(row.get('clicks', 0)),
                int(row.get('conversions', 0))
            ), axis=1
        )
    else:
        df['conversion_rate'] = 0.0
    
    df['engagement_score'] = df.apply(
        lambda row: calculate_engagement_score(
            int(row.get('click_to_view_time_ms', 0)),
            float(row.get('time_to_conversion_sec', 0)) if row.get('time_to_conversion_sec') else None
        ), axis=1
    )
    
    # Google Ads specific features
    df['keyword_fraud_rate'] = df.get('keyword_fraud_rate', 0.0)
    df['target_fraud_rate'] = df.get('target_fraud_rate', 0.0)
    df['gclid_pattern_score'] = df.get('gclid_pattern_score', 0.5)
    
    # Select and order features
    feature_columns = FEATURE_NAMES.copy()
    
    # Check which features exist
    missing_features = [f for f in feature_columns if f not in df.columns]
    if missing_features:
        print(f"  Warning: Missing features (will use defaults): {missing_features}")
        for feat in missing_features:
            df[feat] = 0.0
    
    # Ensure correct order and convert to float
    feature_df = df[FEATURE_NAMES].copy()
    for col in feature_df.columns:
        feature_df[col] = feature_df[col].astype(float)
    
    # Handle missing values if requested (usually done in integration function)
    if preprocess:
        from training.preprocessing import handle_missing_values
        feature_df = handle_missing_values(feature_df, strategy="auto")
    
    # Add label if available
    if 'is_fraud' in df.columns:
        feature_df['is_fraud'] = df['is_fraud']
    elif 'fraud_label' in df.columns:
        feature_df['is_fraud'] = (df['fraud_label'] > 0.5).astype(int)
    
    # Add sample weight if available
    if 'sample_weight' in df.columns:
        feature_df['sample_weight'] = df['sample_weight']
    
    return feature_df


def extract_feature_vector(row: pd.Series, include_google_ads: bool = False) -> List[float]:
    """
    Extract feature vector from a single row (matching production extractor order)
    
    Args:
        row: Series with feature columns
        include_google_ads: If True, include Google Ads specific features
    
    Returns:
        List of feature values in exact order expected by model
    """
    features = []
    
    for feat_name in FEATURE_NAMES:
        if feat_name in row:
            val = row[feat_name]
            # Convert boolean to float
            if isinstance(val, bool):
                features.append(float(1 if val else 0))
            else:
                features.append(float(val) if pd.notna(val) else 0.0)
        else:
            features.append(0.0)
    
    if include_google_ads:
        for feat_name in GOOGLE_ADS_FEATURES:
            if feat_name in row:
                features.append(float(row[feat_name]) if pd.notna(row[feat_name]) else 0.0)
            else:
                features.append(0.0)
    
    return features


def load_and_engineer_features(
    data_source: str = "talkingdata",
    use_sample: bool = True,
    nrows: Optional[int] = None,
    use_chunking: bool = False,
    chunk_size: int = 100000,
    preprocess: bool = True,
    missing_strategy: str = "auto",
    split_data: bool = False,
    train_size: float = 0.7,
    val_size: float = 0.15,
    test_size: float = 0.15,
    stratify: bool = True,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Load data from a source and engineer features in one step
    
    Args:
        data_source: Source name ("talkingdata", "google_ads", "synthetic", "fdb")
        use_sample: For TalkingData, use sample file
        nrows: Limit number of rows to load
        use_chunking: Enable chunked processing for large datasets
        chunk_size: Size of chunks when chunking is enabled
        preprocess: If True, apply preprocessing (missing values, encoding)
        missing_strategy: Strategy for missing value imputation
        split_data: If True, split data into train/val/test sets
        train_size: Proportion for training (default: 0.7)
        val_size: Proportion for validation (default: 0.15)
        test_size: Proportion for testing (default: 0.15)
        stratify: If True, use stratified sampling (default: True)
        random_state: Random seed for reproducibility (default: 42)
    
    Returns:
        DataFrame with engineered and preprocessed features (or dict with train/val/test if split_data=True)
    """
    from training.data_loader import DataLoader
    
    loader = DataLoader()
    
    print(f"Loading data from {data_source}...")
    
    if data_source == "talkingdata":
        df = loader.load_talkingdata(use_sample=use_sample, nrows=nrows)
        features_df = engineer_talkingdata_features(df, use_chunking=use_chunking)
    elif data_source == "google_ads":
        df = loader.load_google_ads_data(limit=nrows)
        features_df = engineer_google_ads_features(df)
    elif data_source == "synthetic":
        df = loader.load_synthetic_data()
        if nrows:
            df = df.head(nrows)
        # Synthetic data may already be in feature format, check and convert if needed
        if all(f in df.columns for f in FEATURE_NAMES):
            features_df = df[FEATURE_NAMES + ['is_fraud']].copy()
        else:
            # Assume TalkingData format for synthetic data
            features_df = engineer_talkingdata_features(df, use_chunking=use_chunking)
    elif data_source.startswith("fdb_"):
        dataset_key = data_source.replace("fdb_", "")
        df = loader.load_fdb_dataset(dataset_key, split="train")
        if nrows:
            df = df.head(nrows)
        # FDB datasets have different formats, may need custom engineering
        # For now, assume similar to TalkingData
        features_df = engineer_talkingdata_features(df, use_chunking=use_chunking)
    else:
        raise ValueError(f"Unknown data source: {data_source}")
    
    # Apply preprocessing if requested
    if preprocess:
        from training.preprocessing import preprocess_features
        features_df, validation = preprocess_features(
            features_df,
            handle_missing=True,
            missing_strategy=missing_strategy,
            encode_categorical=True,
            validate=True
        )
        if not validation.get('valid', True):
            print(f"⚠️  Preprocessing validation warnings: {validation.get('warnings', [])}")
    
    print(f"✅ Engineered {len(features_df):,} rows with {len(FEATURE_NAMES)} features")
    
    # Split data if requested
    if split_data:
        from training.data_splitting import split_data
        train_df, val_df, test_df = split_data(
            features_df,
            train_size=train_size,
            val_size=val_size,
            test_size=test_size,
            stratify=stratify,
            random_state=random_state
        )
        return {
            'train': train_df,
            'validation': val_df,
            'test': test_df,
            'all': features_df  # Include original for reference
        }
    
    return features_df


def validate_features(df: pd.DataFrame, expected_features: List[str] = None) -> Dict[str, Any]:
    """
    Validate that engineered features match expected format
    
    Args:
        df: DataFrame with engineered features
        expected_features: List of expected feature names (defaults to FEATURE_NAMES)
    
    Returns:
        Dictionary with validation results
    """
    if expected_features is None:
        expected_features = FEATURE_NAMES
    
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {}
    }
    
    # Check all expected features exist
    missing_features = [f for f in expected_features if f not in df.columns]
    if missing_features:
        results["valid"] = False
        results["errors"].append(f"Missing features: {missing_features}")
    
    # Check for unexpected features
    unexpected_features = [f for f in df.columns if f not in expected_features and f not in ['is_fraud', 'sample_weight']]
    if unexpected_features:
        results["warnings"].append(f"Unexpected features: {unexpected_features}")
    
    # Check feature types (should be numeric)
    for feat in expected_features:
        if feat in df.columns:
            if not pd.api.types.is_numeric_dtype(df[feat]):
                results["valid"] = False
                results["errors"].append(f"Feature {feat} is not numeric: {df[feat].dtype}")
            
            # Collect statistics
            results["stats"][feat] = {
                "dtype": str(df[feat].dtype),
                "null_count": int(df[feat].isna().sum()),
                "null_pct": float(df[feat].isna().mean() * 100),
                "min": float(df[feat].min()) if pd.api.types.is_numeric_dtype(df[feat]) else None,
                "max": float(df[feat].max()) if pd.api.types.is_numeric_dtype(df[feat]) else None,
                "mean": float(df[feat].mean()) if pd.api.types.is_numeric_dtype(df[feat]) else None,
            }
    
    # Check feature order
    feature_cols = [f for f in expected_features if f in df.columns]
    if feature_cols != expected_features[:len(feature_cols)]:
        results["warnings"].append("Feature order may not match expected order")
    
    # Check label if present
    if 'is_fraud' in df.columns:
        label_dist = df['is_fraud'].value_counts()
        results["stats"]["label_distribution"] = {
            "fraud": int(label_dist.get(1, 0)),
            "legitimate": int(label_dist.get(0, 0)),
            "fraud_pct": float((df['is_fraud'] == 1).mean() * 100)
        }
    
    return results


def main():
    """Example usage"""
    from training.data_loader import DataLoader
    
    loader = DataLoader()
    
    # Example 1: Engineer features from TalkingData (small sample)
    print("=" * 70)
    print("Example 1: Engineering features from TalkingData sample")
    print("=" * 70)
    talkingdata_df = loader.load_talkingdata(use_sample=True, nrows=1000)
    features_df = engineer_talkingdata_features(talkingdata_df, use_chunking=False)
    
    print(f"\n✅ Engineered {len(features_df):,} rows with {len(FEATURE_NAMES)} features")
    print(f"\nFeature columns: {list(features_df.columns)}")
    print(f"\nFirst few rows:")
    print(features_df.head())
    
    # Example 2: Validate features
    print("\n" + "=" * 70)
    print("Example 2: Validating engineered features")
    print("=" * 70)
    validation = validate_features(features_df)
    
    if validation["valid"]:
        print("✅ Feature validation passed!")
    else:
        print("❌ Feature validation failed:")
        for error in validation["errors"]:
            print(f"  - {error}")
    
    if validation["warnings"]:
        print("\n⚠️  Warnings:")
        for warning in validation["warnings"]:
            print(f"  - {warning}")
    
    print(f"\nFeature statistics:")
    for feat, stats in list(validation["stats"].items())[:5]:  # Show first 5
        if isinstance(stats, dict) and "mean" in stats:
            print(f"  {feat}: mean={stats['mean']:.4f}, null_pct={stats['null_pct']:.2f}%")
    
    # Example 3: Using integration function
    print("\n" + "=" * 70)
    print("Example 3: Using load_and_engineer_features integration")
    print("=" * 70)
    try:
        integrated_df = load_and_engineer_features(
            data_source="talkingdata",
            use_sample=True,
            nrows=500,
            use_chunking=False
        )
        print(f"\n✅ Integrated pipeline produced {len(integrated_df):,} rows")
    except Exception as e:
        print(f"\n⚠️  Integration test skipped: {str(e)}")


if __name__ == '__main__':
    main()

