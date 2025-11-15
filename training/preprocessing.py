"""
Data Preprocessing Module for Training Data

Handles:
- Missing value imputation
- Categorical feature encoding
- Data validation and cleaning
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.feature_engineering import FEATURE_NAMES, COUNTRY_CODES, OS_TYPES


# Feature categories for different imputation strategies
NUMERICAL_FEATURES = [
    'ip_click_count_24h',
    'device_click_count_1h',
    'time_since_last_click',
    'hour_of_day',
    'day_of_week',
    'ua_entropy',
    'geo_distance_km',
    'click_to_view_time_ms',
    'campaign_fraud_rate',
    'publisher_quality',
    'device_fingerprint_entropy',
    'time_to_conversion_sec',
    'click_to_install_time_sec',
    'click_injection_risk_score',
    'conversion_rate',
    'engagement_score',
]

BOOLEAN_FEATURES = [
    'ua_is_bot',
    'ip_is_datacenter',
    'ip_is_vpn',
    'ip_is_proxy',
    'ip_is_business',
    'ip_is_competitor',
    'referrer_is_valid',
    'is_mobile',
    'is_repeated_click',
    'has_recent_install',
    'install_broadcast_detected',
]

CATEGORICAL_FEATURES = [
    'ip_country_encoded',
    'device_os_encoded',
]

# Features that should use 0 as default (counts, times, etc.)
ZERO_DEFAULT_FEATURES = [
    'ip_click_count_24h',
    'device_click_count_1h',
    'time_since_last_click',
    'geo_distance_km',
    'click_to_view_time_ms',
    'time_to_conversion_sec',
    'click_to_install_time_sec',
    'conversion_rate',
    'engagement_score',
]

# Features that should use median for missing values (rates, scores)
MEDIAN_DEFAULT_FEATURES = [
    'campaign_fraud_rate',
    'publisher_quality',
    'click_injection_risk_score',
    'ua_entropy',
    'device_fingerprint_entropy',
]


def handle_missing_values(
    df: pd.DataFrame,
    strategy: str = "auto",
    fill_value: Optional[float] = None
) -> pd.DataFrame:
    """
    Handle missing values in feature DataFrame
    
    Args:
        df: DataFrame with features (may contain missing values)
        strategy: Imputation strategy ("auto", "zero", "median", "mean", "mode")
        fill_value: Custom fill value (overrides strategy)
    
    Returns:
        DataFrame with missing values filled
    """
    df = df.copy()
    
    print(f"Handling missing values (strategy: {strategy})...")
    
    # Count missing values before
    missing_before = df.isna().sum().sum()
    if missing_before == 0:
        print("  No missing values found")
        return df
    
    print(f"  Found {missing_before:,} missing values across {df.isna().any().sum()} columns")
    
    # Handle each feature based on its type
    for col in df.columns:
        if col not in FEATURE_NAMES and col not in ['is_fraud', 'sample_weight']:
            continue
        
        missing_count = df[col].isna().sum()
        if missing_count == 0:
            continue
        
        missing_pct = (missing_count / len(df)) * 100
        print(f"    {col}: {missing_count:,} missing ({missing_pct:.2f}%)")
        
        # Determine fill value based on strategy
        if fill_value is not None:
            fill_val = fill_value
        elif strategy == "auto":
            # Auto-select based on feature type
            if col in ZERO_DEFAULT_FEATURES:
                fill_val = 0.0
            elif col in MEDIAN_DEFAULT_FEATURES:
                fill_val = df[col].median() if pd.api.types.is_numeric_dtype(df[col]) else 0.0
            elif col in BOOLEAN_FEATURES:
                fill_val = False
            elif col in CATEGORICAL_FEATURES:
                fill_val = 0  # Default encoded value
            else:
                fill_val = 0.0
        elif strategy == "zero":
            fill_val = 0.0
        elif strategy == "median":
            fill_val = df[col].median() if pd.api.types.is_numeric_dtype(df[col]) else 0.0
        elif strategy == "mean":
            fill_val = df[col].mean() if pd.api.types.is_numeric_dtype(df[col]) else 0.0
        elif strategy == "mode":
            fill_val = df[col].mode()[0] if len(df[col].mode()) > 0 else 0.0
        else:
            fill_val = 0.0
        
        # Fill missing values
        df[col] = df[col].fillna(fill_val).infer_objects(copy=False)
        print(f"      → Filled with {fill_val}")
    
    # Verify no missing values remain
    missing_after = df.isna().sum().sum()
    if missing_after > 0:
        print(f"  ⚠️  Warning: {missing_after:,} missing values still remain")
    else:
        print(f"  ✅ All missing values handled")
    
    return df


def encode_categorical_features(
    df: pd.DataFrame,
    country_column: Optional[str] = None,
    os_column: Optional[str] = None,
    validate: bool = True
) -> pd.DataFrame:
    """
    Encode categorical features to match production extractor
    
    Args:
        df: DataFrame with raw or partially processed features
        country_column: Name of country column (if not already encoded)
        os_column: Name of OS column (if not already encoded)
        validate: If True, validate encoding matches expected format
    
    Returns:
        DataFrame with categorical features encoded
    """
    df = df.copy()
    
    print("Encoding categorical features...")
    
    # Encode country if raw country column exists
    if country_column and country_column in df.columns:
        if 'ip_country_encoded' not in df.columns:
            print(f"  Encoding {country_column} → ip_country_encoded")
            df['ip_country_encoded'] = df[country_column].apply(
                lambda c: COUNTRY_CODES.index(c) if c in COUNTRY_CODES else 0
            )
            # Drop original column
            df = df.drop(columns=[country_column])
        else:
            print(f"  ip_country_encoded already exists, skipping {country_column}")
    
    # Encode OS if raw OS column exists
    if os_column and os_column in df.columns:
        if 'device_os_encoded' not in df.columns:
            print(f"  Encoding {os_column} → device_os_encoded")
            df['device_os_encoded'] = df[os_column].apply(
                lambda os: OS_TYPES.index(os) if os in OS_TYPES else 0
            )
            # Drop original column
            df = df.drop(columns=[os_column])
        else:
            print(f"  device_os_encoded already exists, skipping {os_column}")
    
    # Ensure encoded columns exist
    if 'ip_country_encoded' not in df.columns:
        print("  Creating ip_country_encoded (default: 0)")
        df['ip_country_encoded'] = 0
    
    if 'device_os_encoded' not in df.columns:
        print("  Creating device_os_encoded (default: 0)")
        df['device_os_encoded'] = 0
    
    # Validate encoding
    if validate:
        if 'ip_country_encoded' in df.columns:
            invalid_countries = ~df['ip_country_encoded'].isin(range(len(COUNTRY_CODES)))
            if invalid_countries.sum() > 0:
                print(f"  ⚠️  Warning: {invalid_countries.sum()} invalid country encodings (will use 0)")
                df.loc[invalid_countries, 'ip_country_encoded'] = 0
        
        if 'device_os_encoded' in df.columns:
            invalid_os = ~df['device_os_encoded'].isin(range(len(OS_TYPES)))
            if invalid_os.sum() > 0:
                print(f"  ⚠️  Warning: {invalid_os.sum()} invalid OS encodings (will use 0)")
                df.loc[invalid_os, 'device_os_encoded'] = 0
    
    print("  ✅ Categorical encoding complete")
    return df


def validate_preprocessed_data(
    df: pd.DataFrame,
    check_missing: bool = True,
    check_types: bool = True,
    check_ranges: bool = True,
    check_infinite: bool = True
) -> Dict[str, Any]:
    """
    Validate preprocessed data
    
    Args:
        df: DataFrame to validate
        check_missing: Check for missing values
        check_types: Check data types
        check_ranges: Check value ranges
        check_infinite: Check for infinite values
    
    Returns:
        Dictionary with validation results
    """
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {}
    }
    
    print("Validating preprocessed data...")
    
    # Check for missing values
    if check_missing:
        missing = df.isna().sum()
        missing_cols = missing[missing > 0]
        if len(missing_cols) > 0:
            results["valid"] = False
            results["errors"].append(f"Missing values found in {len(missing_cols)} columns: {list(missing_cols.index)}")
            for col, count in missing_cols.items():
                results["stats"][f"{col}_missing"] = int(count)
        else:
            print("  ✅ No missing values")
    
    # Check data types
    if check_types:
        for col in df.columns:
            if col in FEATURE_NAMES:
                if not pd.api.types.is_numeric_dtype(df[col]):
                    results["valid"] = False
                    results["errors"].append(f"Column {col} is not numeric: {df[col].dtype}")
                else:
                    results["stats"][f"{col}_dtype"] = str(df[col].dtype)
        print("  ✅ Data types validated")
    
    # Check for infinite values
    if check_infinite:
        for col in df.columns:
            if col in FEATURE_NAMES and pd.api.types.is_numeric_dtype(df[col]):
                inf_count = np.isinf(df[col]).sum()
                if inf_count > 0:
                    results["valid"] = False
                    results["errors"].append(f"Column {col} has {inf_count} infinite values")
                    results["stats"][f"{col}_infinite"] = int(inf_count)
        
        if not any("infinite" in str(e) for e in results["errors"]):
            print("  ✅ No infinite values")
    
    # Check value ranges
    if check_ranges:
        for col in df.columns:
            if col in FEATURE_NAMES and pd.api.types.is_numeric_dtype(df[col]):
                min_val = df[col].min()
                max_val = df[col].max()
                results["stats"][f"{col}_range"] = {"min": float(min_val), "max": float(max_val)}
                
                # Warn about unusual ranges
                if col in BOOLEAN_FEATURES and not (min_val in [0, 1] and max_val in [0, 1]):
                    results["warnings"].append(f"Boolean feature {col} has values outside [0, 1]: [{min_val}, {max_val}]")
                elif col in CATEGORICAL_FEATURES:
                    if col == 'ip_country_encoded' and max_val >= len(COUNTRY_CODES):
                        results["warnings"].append(f"Country encoding {col} has values >= {len(COUNTRY_CODES)}")
                    elif col == 'device_os_encoded' and max_val >= len(OS_TYPES):
                        results["warnings"].append(f"OS encoding {col} has values >= {len(OS_TYPES)}")
        
        print("  ✅ Value ranges checked")
    
    if results["valid"]:
        print("  ✅ All validation checks passed")
    else:
        print(f"  ❌ Validation failed: {len(results['errors'])} errors")
    
    return results


def preprocess_features(
    df: pd.DataFrame,
    handle_missing: bool = True,
    missing_strategy: str = "auto",
    encode_categorical: bool = True,
    country_column: Optional[str] = None,
    os_column: Optional[str] = None,
    validate: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Complete preprocessing pipeline for feature DataFrame
    
    Args:
        df: DataFrame with features (may have missing values, unencoded categoricals)
        handle_missing: If True, handle missing values
        missing_strategy: Strategy for missing value imputation
        encode_categorical: If True, encode categorical features
        country_column: Name of raw country column (if exists)
        os_column: Name of raw OS column (if exists)
        validate: If True, validate preprocessed data
    
    Returns:
        Tuple of (preprocessed DataFrame, validation results)
    """
    print("=" * 70)
    print("Preprocessing Features")
    print("=" * 70)
    
    df = df.copy()
    
    # Step 1: Encode categorical features (before handling missing values)
    if encode_categorical:
        df = encode_categorical_features(
            df,
            country_column=country_column,
            os_column=os_column,
            validate=validate
        )
    
    # Step 2: Handle missing values
    if handle_missing:
        df = handle_missing_values(df, strategy=missing_strategy)
    
    # Step 3: Validate
    validation_results = None
    if validate:
        validation_results = validate_preprocessed_data(df)
    
    print("=" * 70)
    print("Preprocessing Complete")
    print("=" * 70)
    
    return df, validation_results or {}


def main():
    """Example usage"""
    from training.data_loader import DataLoader
    from training.feature_engineering import engineer_talkingdata_features
    
    loader = DataLoader()
    
    # Load and engineer features
    print("Loading and engineering features...")
    if loader.check_talkingdata_available():
        df = loader.load_talkingdata(use_sample=True, nrows=100)
        features_df = engineer_talkingdata_features(df, use_chunking=False)
        
        # Preprocess
        preprocessed_df, validation = preprocess_features(
            features_df,
            handle_missing=True,
            missing_strategy="auto",
            encode_categorical=True,
            validate=True
        )
        
        print(f"\n✅ Preprocessed {len(preprocessed_df):,} rows")
        print(f"Validation passed: {validation.get('valid', False)}")
        
        if validation.get('warnings'):
            print("\nWarnings:")
            for warning in validation['warnings']:
                print(f"  - {warning}")
    else:
        print("⚠️  TalkingData files not available for testing")


if __name__ == '__main__':
    main()

