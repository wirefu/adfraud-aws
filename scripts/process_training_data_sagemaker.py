#!/usr/bin/env python3
"""
SageMaker Processing Job Entry Point

This script runs inside a SageMaker Processing Job to process training data.
It reads raw data from S3, engineers features, and writes processed data back to S3.

Usage (inside SageMaker Processing Job):
    python process_training_data_sagemaker.py \
        --input-data-source talkingdata \
        --input-s3-path s3://bucket/fraud-detection/training/raw/ \
        --output-s3-path s3://bucket/fraud-detection/training/processed/ \
        --use-smote \
        --compress
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

# Add parent directory to path for imports
# In SageMaker Processing, the code is in /opt/ml/processing/input/code/
sys.path.insert(0, '/opt/ml/processing/input/code')
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.feature_engineering import (
    load_and_engineer_features,
    FEATURE_NAMES
)
from scripts.process_training_data import (
    format_for_sagemaker,
    calculate_class_imbalance_metrics,
    apply_smote,
    save_to_csv_sagemaker_format,
)


def load_data_from_s3(s3_path: str, data_source: str, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Load raw data from S3
    
    Args:
        s3_path: S3 path to raw data (e.g., s3://bucket/fraud-detection/training/raw/)
        data_source: Data source name ("talkingdata", etc.)
        nrows: Limit number of rows (for testing)
    
    Returns:
        DataFrame with raw data
    """
    import boto3
    
    s3_client = boto3.client('s3')
    
    # Parse S3 path
    s3_path = s3_path.replace('s3://', '')
    bucket, prefix = s3_path.split('/', 1)
    
    if not prefix.endswith('/'):
        prefix += '/'
    
    # Determine file to load based on data source
    if data_source == 'talkingdata':
        file_key = f"{prefix}train.csv"
    else:
        file_key = f"{prefix}{data_source}.csv"
    
    print(f"Loading data from s3://{bucket}/{file_key}...")
    
    # Download file to local processing directory
    local_file = f"/opt/ml/processing/input/data/{os.path.basename(file_key)}"
    os.makedirs(os.path.dirname(local_file), exist_ok=True)
    
    try:
        s3_client.download_file(bucket, file_key, local_file)
        print(f"  ✅ Downloaded to {local_file}")
        
        # Load CSV
        df = pd.read_csv(local_file, nrows=nrows)
        print(f"  ✅ Loaded {len(df):,} rows")
        
        return df
    except Exception as e:
        print(f"  ❌ Error loading data: {e}")
        raise


def save_data_to_s3(df: pd.DataFrame, s3_path: str, filename: str, compress: bool = False) -> str:
    """
    Save DataFrame to S3
    
    Args:
        df: DataFrame to save
        s3_path: S3 output path
        filename: Output filename
        compress: If True, compress with gzip
    
    Returns:
        S3 URI of saved file
    """
    import boto3
    
    s3_client = boto3.client('s3')
    
    # Parse S3 path
    s3_path = s3_path.replace('s3://', '')
    bucket, prefix = s3_path.split('/', 1)
    
    if not prefix.endswith('/'):
        prefix += '/'
    
    # Save to local processing directory first
    output_dir = '/opt/ml/processing/output'
    os.makedirs(output_dir, exist_ok=True)
    
    local_file = os.path.join(output_dir, filename)
    
    # Save CSV
    save_to_csv_sagemaker_format(local_file, df, compress=compress)
    
    # Upload to S3
    s3_key = f"{prefix}{filename}"
    if compress:
        s3_key += ".gz"
    
    print(f"Uploading to s3://{bucket}/{s3_key}...")
    s3_client.upload_file(local_file, bucket, s3_key)
    print(f"  ✅ Uploaded to s3://{bucket}/{s3_key}")
    
    return f"s3://{bucket}/{s3_key}"


def process_training_data_sagemaker(
    input_s3_path: str,
    output_s3_path: str,
    data_source: str = "talkingdata",
    nrows: Optional[int] = None,
    use_smote: bool = False,
    compress: bool = False,
    train_size: float = 0.7,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42
) -> Dict:
    """
    Process training data in SageMaker Processing Job
    
    Args:
        input_s3_path: S3 path to raw input data
        output_s3_path: S3 path for processed output data
        data_source: Data source name
        nrows: Limit number of rows (for testing)
        use_smote: Apply SMOTE oversampling
        compress: Compress output files
        train_size: Training set proportion
        val_size: Validation set proportion
        test_size: Test set proportion
        random_state: Random seed
    
    Returns:
        Dictionary with processing results
    """
    print("=" * 70)
    print("SageMaker Processing Job: Training Data Processing")
    print("=" * 70)
    print(f"Input S3: {input_s3_path}")
    print(f"Output S3: {output_s3_path}")
    print(f"Data source: {data_source}")
    if nrows:
        print(f"Row limit: {nrows:,}")
    print()
    
    # Step 1: Load raw data from S3
    print("Step 1: Loading raw data from S3...")
    raw_df = load_data_from_s3(input_s3_path, data_source, nrows)
    print()
    
    # Step 2: Engineer features
    print("Step 2: Engineering features...")
    from training.feature_engineering import engineer_talkingdata_features
    from training.preprocessing import preprocess_features
    from training.data_splitting import split_data
    
    # Engineer features based on data source
    if data_source == 'talkingdata':
        features_df = engineer_talkingdata_features(raw_df, use_chunking=True)
        # Preprocess
        features_df, _ = preprocess_features(features_df)
    else:
        # For other sources, save raw data temporarily and use load_and_engineer_features
        # This is a workaround - ideally we'd have source-specific engineering functions
        temp_file = '/opt/ml/processing/input/data/temp_raw.csv'
        raw_df.to_csv(temp_file, index=False)
        
        # Use the general function (note: this may need adjustment for non-TalkingData sources)
        splits = load_and_engineer_features(
            data_source=data_source,
            use_sample=False,
            nrows=nrows,
            use_chunking=True,
            preprocess=True,
            split_data=True,
            train_size=train_size,
            val_size=val_size,
            test_size=test_size,
            stratify=True,
            random_state=random_state
        )
        train_df = splits['train']
        val_df = splits['validation']
        test_df = splits['test']
        
        # Skip to metrics calculation
        print(f"✅ Engineered features: {len(train_df):,} train, {len(val_df):,} val, {len(test_df):,} test")
        print()
        
        # Calculate metrics
        train_metrics = calculate_class_imbalance_metrics(train_df)
        
        # Apply SMOTE if requested
        if use_smote:
            print("Step 3: Applying SMOTE oversampling...")
            X_train = train_df.drop(columns=['is_fraud'])
            y_train = train_df['is_fraud']
            X_train_resampled, y_train_resampled = apply_smote(X_train, y_train, random_state)
            train_df = pd.concat([X_train_resampled, y_train_resampled], axis=1)
            train_df.columns = list(X_train.columns) + ['is_fraud']
            train_metrics = calculate_class_imbalance_metrics(train_df)
            print(f"  ✅ After SMOTE: {len(train_df):,} samples")
            print()
        
        # Format for SageMaker
        train_sagemaker = format_for_sagemaker(train_df)
        val_sagemaker = format_for_sagemaker(val_df)
        test_sagemaker = format_for_sagemaker(test_df)
        
        # Save to S3
        print("Step 4: Saving processed data to S3...")
        train_uri = save_data_to_s3(train_sagemaker, output_s3_path, 'train.csv', compress)
        val_uri = save_data_to_s3(val_sagemaker, output_s3_path, 'val.csv', compress)
        test_uri = save_data_to_s3(test_sagemaker, output_s3_path, 'test.csv', compress)
        
        # Save metrics
        metrics = {
            'train': train_metrics,
            'validation': calculate_class_imbalance_metrics(val_df),
            'test': calculate_class_imbalance_metrics(test_df),
            'scale_pos_weight': train_metrics['scale_pos_weight'],
            'feature_count': len(FEATURE_NAMES),
            'feature_names': FEATURE_NAMES
        }
        
        metrics_json = json.dumps(metrics, indent=2)
        metrics_file = '/opt/ml/processing/output/metrics.json'
        with open(metrics_file, 'w') as f:
            f.write(metrics_json)
        
        # Upload metrics
        import boto3
        s3_client = boto3.client('s3')
        s3_path = output_s3_path.replace('s3://', '')
        bucket, prefix = s3_path.split('/', 1)
        if not prefix.endswith('/'):
            prefix += '/'
        s3_client.upload_file(metrics_file, bucket, f"{prefix}metrics.json")
        
        print("  ✅ Saved metrics.json")
        print()
        
        return {
            'train_samples': len(train_df),
            'val_samples': len(val_df),
            'test_samples': len(test_df),
            'scale_pos_weight': train_metrics['scale_pos_weight'],
            'output_files': {
                'train': train_uri,
                'validation': val_uri,
                'test': test_uri,
                'metrics': f"s3://{bucket}/{prefix}metrics.json"
            }
        }
    
    # For TalkingData, continue with feature engineering
    print(f"✅ Engineered {len(features_df):,} rows with {len(FEATURE_NAMES)} features")
    print()
    
    # Step 3: Split data
    print("Step 3: Splitting data...")
    from training.data_splitting import split_data
    
    splits = split_data(
        features_df,
        train_size=train_size,
        val_size=val_size,
        test_size=test_size,
        stratify=True,
        random_state=random_state
    )
    
    train_df = splits['train']
    val_df = splits['validation']
    test_df = splits['test']
    
    print(f"✅ Split: {len(train_df):,} train, {len(val_df):,} val, {len(test_df):,} test")
    print()
    
    # Step 4: Calculate metrics
    print("Step 4: Calculating class imbalance metrics...")
    train_metrics = calculate_class_imbalance_metrics(train_df)
    val_metrics = calculate_class_imbalance_metrics(val_df)
    test_metrics = calculate_class_imbalance_metrics(test_df)
    
    print(f"  Train - Fraud: {train_metrics['num_fraud']:,} ({train_metrics['fraud_rate']:.2%}), "
          f"Legitimate: {train_metrics['num_legitimate']:,} ({train_metrics['legitimate_rate']:.2%})")
    print(f"  Scale pos weight: {train_metrics['scale_pos_weight']:.4f}")
    print()
    
    # Step 5: Apply SMOTE if requested
    if use_smote:
        print("Step 5: Applying SMOTE oversampling...")
        X_train = train_df.drop(columns=['is_fraud'])
        y_train = train_df['is_fraud']
        
        X_train_resampled, y_train_resampled = apply_smote(X_train, y_train, random_state)
        
        train_df = pd.concat([X_train_resampled, y_train_resampled], axis=1)
        train_df.columns = list(X_train.columns) + ['is_fraud']
        
        train_metrics = calculate_class_imbalance_metrics(train_df)
        print(f"  ✅ After SMOTE: {len(train_df):,} samples")
        print()
    
    # Step 6: Format for SageMaker
    print("Step 6: Formatting for SageMaker...")
    train_sagemaker = format_for_sagemaker(train_df)
    val_sagemaker = format_for_sagemaker(val_df)
    test_sagemaker = format_for_sagemaker(test_df)
    
    print(f"  ✅ Formatted: {len(FEATURE_NAMES)} features + label")
    print()
    
    # Step 7: Save to S3
    print("Step 7: Saving processed data to S3...")
    train_uri = save_data_to_s3(train_sagemaker, output_s3_path, 'train.csv', compress)
    val_uri = save_data_to_s3(val_sagemaker, output_s3_path, 'val.csv', compress)
    test_uri = save_data_to_s3(test_sagemaker, output_s3_path, 'test.csv', compress)
    
    # Save metrics
    metrics = {
        'train': train_metrics,
        'validation': val_metrics,
        'test': test_metrics,
        'scale_pos_weight': train_metrics['scale_pos_weight'],
        'feature_count': len(FEATURE_NAMES),
        'feature_names': FEATURE_NAMES
    }
    
    metrics_json = json.dumps(metrics, indent=2)
    metrics_file = '/opt/ml/processing/output/metrics.json'
    with open(metrics_file, 'w') as f:
        f.write(metrics_json)
    
    # Upload metrics
    import boto3
    s3_client = boto3.client('s3')
    s3_path = output_s3_path.replace('s3://', '')
    bucket, prefix = s3_path.split('/', 1)
    if not prefix.endswith('/'):
        prefix += '/'
    s3_client.upload_file(metrics_file, bucket, f"{prefix}metrics.json")
    
    print("  ✅ Saved metrics.json")
    print()
    
    # Summary
    print("=" * 70)
    print("Processing Complete!")
    print("=" * 70)
    print(f"Train samples: {len(train_df):,}")
    print(f"Validation samples: {len(val_df):,}")
    print(f"Test samples: {len(test_df):,}")
    print(f"Scale pos weight: {train_metrics['scale_pos_weight']:.4f}")
    print(f"Features: {len(FEATURE_NAMES)}")
    print("\nOutput files:")
    print(f"  train: {train_uri}")
    print(f"  validation: {val_uri}")
    print(f"  test: {test_uri}")
    print(f"  metrics: s3://{bucket}/{prefix}metrics.json")
    
    return {
        'train_samples': len(train_df),
        'val_samples': len(val_df),
        'test_samples': len(test_df),
        'scale_pos_weight': train_metrics['scale_pos_weight'],
        'output_files': {
            'train': train_uri,
            'validation': val_uri,
            'test': test_uri,
            'metrics': f"s3://{bucket}/{prefix}metrics.json"
        }
    }


def main():
    """Main entry point for SageMaker Processing Job"""
    parser = argparse.ArgumentParser(
        description='Process training data in SageMaker Processing Job'
    )
    
    parser.add_argument(
        '--input-data-source',
        type=str,
        default='talkingdata',
        help='Data source name (default: talkingdata)'
    )
    
    parser.add_argument(
        '--input-s3-path',
        type=str,
        required=True,
        help='S3 path to raw input data (e.g., s3://bucket/fraud-detection/training/raw/)'
    )
    
    parser.add_argument(
        '--output-s3-path',
        type=str,
        required=True,
        help='S3 path for processed output data (e.g., s3://bucket/fraud-detection/training/processed/)'
    )
    
    parser.add_argument(
        '--nrows',
        type=int,
        default=None,
        help='Limit number of rows to process (for testing)'
    )
    
    parser.add_argument(
        '--use-smote',
        action='store_true',
        help='Apply SMOTE oversampling'
    )
    
    parser.add_argument(
        '--compress',
        action='store_true',
        help='Compress output files with gzip'
    )
    
    parser.add_argument(
        '--train-size',
        type=float,
        default=0.7,
        help='Training set proportion (default: 0.7)'
    )
    
    parser.add_argument(
        '--val-size',
        type=float,
        default=0.15,
        help='Validation set proportion (default: 0.15)'
    )
    
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.15,
        help='Test set proportion (default: 0.15)'
    )
    
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help='Random seed (default: 42)'
    )
    
    args = parser.parse_args()
    
    # Validate split sizes
    total_size = args.train_size + args.val_size + args.test_size
    if not np.isclose(total_size, 1.0, atol=1e-6):
        parser.error(f"Split sizes must sum to 1.0, got {total_size:.6f}")
    
    try:
        results = process_training_data_sagemaker(
            input_s3_path=args.input_s3_path,
            output_s3_path=args.output_s3_path,
            data_source=args.input_data_source,
            nrows=args.nrows,
            use_smote=args.use_smote,
            compress=args.compress,
            train_size=args.train_size,
            val_size=args.val_size,
            test_size=args.test_size,
            random_state=args.random_state
        )
        
        print("\n✅ Processing job completed successfully!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

