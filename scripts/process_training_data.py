#!/usr/bin/env python3
"""
Process Training Data for SageMaker

Orchestrates feature engineering, preprocessing, and data preparation
for SageMaker XGBoost training.

Usage:
    python scripts/process_training_data.py \
        --data-source talkingdata \
        --output s3://bucket/fraud-detection/training/processed/ \
        --nrows 10000 \
        --use-smote \
        --compress
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
import math

import boto3
import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.feature_engineering import (
    load_and_engineer_features,
    FEATURE_NAMES
)


def format_for_sagemaker(
    df: pd.DataFrame,
    label_column: str = 'is_fraud',
    feature_names: Optional[list] = None
) -> pd.DataFrame:
    """
    Format DataFrame for SageMaker XGBoost format
    
    Requirements:
    - CSV format with NO header row
    - Features in exact order matching production feature extractor
    - Label as LAST column (0 = legitimate, 1 = fraud)
    - All numerical values, comma-separated
    
    Args:
        df: DataFrame with features and labels
        label_column: Name of label column (default: 'is_fraud')
        feature_names: List of feature names in order (default: FEATURE_NAMES)
    
    Returns:
        DataFrame formatted for SageMaker (features + label, in correct order)
    """
    if feature_names is None:
        feature_names = FEATURE_NAMES
    
    df = df.copy()
    
    # Validate label column exists
    if label_column not in df.columns:
        raise ValueError(f"Label column '{label_column}' not found in DataFrame")
    
    # Ensure all feature columns exist (fill missing with 0.0)
    missing_features = [f for f in feature_names if f not in df.columns]
    if missing_features:
        print(f"  ⚠️  Missing features (filling with 0.0): {missing_features}")
        for feat in missing_features:
            df[feat] = 0.0
    
    # Select features in correct order
    feature_df = df[feature_names].copy()
    
    # Validate all values are numerical
    for col in feature_df.columns:
        if not pd.api.types.is_numeric_dtype(feature_df[col]):
            raise ValueError(f"Feature '{col}' is not numerical: {feature_df[col].dtype}")
    
    # Handle infinite values (replace with large finite value)
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
    feature_df = feature_df.fillna(0.0)
    
    # Ensure all values are finite
    if not np.isfinite(feature_df.values).all():
        print("  ⚠️  Warning: Some values are not finite, replacing with 0.0")
        feature_df = feature_df.replace([np.inf, -np.inf, np.nan], 0.0)
    
    # Convert to float
    for col in feature_df.columns:
        feature_df[col] = feature_df[col].astype(float)
    
    # Add label as last column
    label_series = df[label_column].astype(int)
    
    # Combine features and label
    sagemaker_df = pd.concat([feature_df, label_series], axis=1)
    
    # Rename label column to match expected format
    sagemaker_df.columns = list(feature_names) + ['label']
    
    return sagemaker_df


def calculate_class_imbalance_metrics(df: pd.DataFrame, label_column: str = 'is_fraud') -> Dict:
    """
    Calculate class imbalance metrics for XGBoost
    
    Args:
        df: DataFrame with labels
        label_column: Name of label column
    
    Returns:
        Dictionary with class distribution and scale_pos_weight
    """
    if label_column not in df.columns:
        raise ValueError(f"Label column '{label_column}' not found")
    
    label_counts = df[label_column].value_counts().sort_index()
    label_pct = df[label_column].value_counts(normalize=True).sort_index() * 100
    
    num_fraud = int(label_counts.get(1, 0))
    num_legitimate = int(label_counts.get(0, 0))
    total = len(df)
    
    # Calculate scale_pos_weight for XGBoost
    if num_fraud > 0:
        # Use sqrt of ratio (less aggressive than direct ratio)
        scale_pos_weight = math.sqrt(num_legitimate / num_fraud)
    else:
        scale_pos_weight = 1.0
        print("  ⚠️  Warning: No fraud samples found, scale_pos_weight set to 1.0")
    
    metrics = {
        'total_samples': int(total),
        'num_fraud': num_fraud,
        'num_legitimate': num_legitimate,
        'fraud_rate': float(num_fraud / total) if total > 0 else 0.0,
        'legitimate_rate': float(num_legitimate / total) if total > 0 else 0.0,
        'scale_pos_weight': float(scale_pos_weight),
        'class_distribution': {
            'fraud': {
                'count': num_fraud,
                'percentage': float(label_pct.get(1, 0.0))
            },
            'legitimate': {
                'count': num_legitimate,
                'percentage': float(label_pct.get(0, 0.0))
            }
        }
    }
    
    return metrics


def apply_smote(
    X: pd.DataFrame,
    y: pd.Series,
    random_state: int = 42
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Apply SMOTE oversampling to handle class imbalance
    
    Args:
        X: Feature DataFrame
        y: Label Series
        random_state: Random seed
    
    Returns:
        Tuple of (X_resampled, y_resampled)
    """
    try:
        from imblearn.over_sampling import SMOTE
    except ImportError:
        raise ImportError(
            "imbalanced-learn is required for SMOTE. Install with: pip install imbalanced-learn"
        )
    
    print("  Applying SMOTE oversampling...")
    
    smote = SMOTE(random_state=random_state)
    X_resampled, y_resampled = smote.fit_resample(X, y)
    
    print(f"  ✅ Resampled: {len(X)} -> {len(X_resampled)} samples")
    
    # Convert back to DataFrame/Series
    X_resampled_df = pd.DataFrame(X_resampled, columns=X.columns)
    y_resampled_series = pd.Series(y_resampled, name=y.name)
    
    return X_resampled_df, y_resampled_series


def save_to_csv_sagemaker_format(
    filepath: str,
    df: pd.DataFrame,
    compress: bool = False
) -> str:
    """
    Save DataFrame to CSV in SageMaker format (no header, label last)
    
    Args:
        filepath: Output file path
        df: DataFrame formatted for SageMaker
        compress: If True, compress with gzip
    
    Returns:
        Path to saved file
    """
    if compress:
        if not filepath.endswith('.gz'):
            filepath += '.gz'
        compression = 'gzip'
    else:
        compression = None
    
    # Save without header, index, or column names
    df.to_csv(
        filepath,
        header=False,
        index=False,
        compression=compression
    )
    
    file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
    print(f"  ✅ Saved: {filepath} ({file_size:.2f} MB)")
    
    return filepath


def upload_to_s3(
    local_file: str,
    s3_path: str,
    bucket: Optional[str] = None,
    key: Optional[str] = None
) -> str:
    """
    Upload file to S3
    
    Args:
        local_file: Local file path
        s3_path: Full S3 path (s3://bucket/key) or just key
        bucket: S3 bucket name (if not in s3_path)
        key: S3 key (if not in s3_path)
    
    Returns:
        S3 URI of uploaded file
    """
    s3_client = boto3.client('s3')
    
    # Parse S3 path
    if s3_path.startswith('s3://'):
        # Extract bucket and key from s3:// path
        s3_path = s3_path[5:]  # Remove 's3://'
        parts = s3_path.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else os.path.basename(local_file)
    else:
        # Use s3_path as key
        if not bucket:
            raise ValueError("Bucket must be provided if s3_path is not a full S3 URI")
        key = s3_path
    
    # Ensure key ends with filename if it's a directory
    if key.endswith('/'):
        key = key + os.path.basename(local_file)
    
    print(f"  Uploading {local_file} to s3://{bucket}/{key}...")
    
    s3_client.upload_file(local_file, bucket, key)
    
    s3_uri = f"s3://{bucket}/{key}"
    print(f"  ✅ Uploaded: {s3_uri}")
    
    return s3_uri


def process_training_data(
    data_source: str = "talkingdata",
    output_path: str = None,
    nrows: Optional[int] = None,
    use_sample: bool = True,
    use_chunking: bool = False,
    use_smote: bool = False,
    compress: bool = False,
    train_size: float = 0.7,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42
) -> Dict:
    """
    Process training data end-to-end for SageMaker
    
    Args:
        data_source: Data source name ("talkingdata", "fdb_*", "synthetic", "google_ads")
        output_path: Output path (S3 URI or local directory)
        nrows: Limit number of rows (for testing)
        use_sample: For TalkingData, use sample file
        use_chunking: Enable chunked processing for large datasets
        use_smote: Apply SMOTE oversampling
        compress: Compress output files with gzip
        train_size: Training set proportion
        val_size: Validation set proportion
        test_size: Test set proportion
        random_state: Random seed
    
    Returns:
        Dictionary with processing results and metrics
    """
    print("=" * 70)
    print("Processing Training Data for SageMaker")
    print("=" * 70)
    print(f"Data source: {data_source}")
    print(f"Output: {output_path}")
    if nrows:
        print(f"Row limit: {nrows:,}")
    print()
    
    # Step 1: Load and engineer features
    print("Step 1: Loading and engineering features...")
    splits = load_and_engineer_features(
        data_source=data_source,
        use_sample=use_sample,
        nrows=nrows,
        use_chunking=use_chunking,
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
    
    print(f"✅ Loaded and split: {len(train_df):,} train, {len(val_df):,} val, {len(test_df):,} test")
    print()
    
    # Step 2: Calculate class imbalance metrics
    print("Step 2: Calculating class imbalance metrics...")
    train_metrics = calculate_class_imbalance_metrics(train_df)
    val_metrics = calculate_class_imbalance_metrics(val_df)
    test_metrics = calculate_class_imbalance_metrics(test_df)
    
    print(f"  Train - Fraud: {train_metrics['num_fraud']:,} ({train_metrics['fraud_rate']:.2%}), "
          f"Legitimate: {train_metrics['num_legitimate']:,} ({train_metrics['legitimate_rate']:.2%})")
    print(f"  Scale pos weight: {train_metrics['scale_pos_weight']:.4f}")
    print()
    
    # Step 3: Apply SMOTE if requested
    if use_smote:
        print("Step 3: Applying SMOTE oversampling...")
        X_train = train_df.drop(columns=['is_fraud'])
        y_train = train_df['is_fraud']
        
        X_train_resampled, y_train_resampled = apply_smote(X_train, y_train, random_state)
        
        # Reconstruct DataFrame
        train_df = pd.concat([X_train_resampled, y_train_resampled], axis=1)
        train_df.columns = list(X_train.columns) + ['is_fraud']
        
        # Recalculate metrics after SMOTE
        train_metrics = calculate_class_imbalance_metrics(train_df)
        print(f"  ✅ After SMOTE: {len(train_df):,} samples")
        print()
    
    # Step 4: Format for SageMaker
    print("Step 4: Formatting for SageMaker...")
    train_sagemaker = format_for_sagemaker(train_df)
    val_sagemaker = format_for_sagemaker(val_df)
    test_sagemaker = format_for_sagemaker(test_df)
    
    print(f"  ✅ Formatted: {len(train_sagemaker)} features + label")
    print()
    
    # Step 5: Save files
    print("Step 5: Saving files...")
    
    # Determine if output is S3 or local
    is_s3 = output_path and output_path.startswith('s3://')
    
    if is_s3:
        # Save to temporary local directory first
        temp_dir = Path('/tmp/training_data')
        temp_dir.mkdir(exist_ok=True)
        
        train_file = str(temp_dir / 'train.csv')
        val_file = str(temp_dir / 'val.csv')
        test_file = str(temp_dir / 'test.csv')
        metrics_file = str(temp_dir / 'metrics.json')
    else:
        # Save to local directory
        if output_path:
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = Path('.')
        
        train_file = str(output_dir / 'train.csv')
        val_file = str(output_dir / 'val.csv')
        test_file = str(output_dir / 'test.csv')
        metrics_file = str(output_dir / 'metrics.json')
    
    # Save CSV files (returns actual file path, which may include .gz extension)
    train_file_actual = save_to_csv_sagemaker_format(train_file, train_sagemaker, compress=compress)
    val_file_actual = save_to_csv_sagemaker_format(val_file, val_sagemaker, compress=compress)
    test_file_actual = save_to_csv_sagemaker_format(test_file, test_sagemaker, compress=compress)
    
    # Save metrics
    all_metrics = {
        'train': train_metrics,
        'validation': val_metrics,
        'test': test_metrics,
        'scale_pos_weight': train_metrics['scale_pos_weight'],
        'feature_count': len(FEATURE_NAMES),
        'feature_names': FEATURE_NAMES
    }
    
    with open(metrics_file, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    
    print(f"  ✅ Saved metrics: {metrics_file}")
    print()
    
    # Step 6: Upload to S3 if needed
    uploaded_files = {}
    if is_s3:
        print("Step 6: Uploading to S3...")
        
        # Parse S3 path
        s3_path = output_path[5:]  # Remove 's3://'
        parts = s3_path.split('/', 1)
        s3_bucket = parts[0]
        s3_prefix = parts[1] if len(parts) > 1 else 'processed/'
        
        if not s3_prefix.endswith('/'):
            s3_prefix += '/'
        
        # Upload files (use actual file paths which may include .gz)
        uploaded_files['train'] = upload_to_s3(
            train_file_actual,
            f"s3://{s3_bucket}/{s3_prefix}train.csv" + ('.gz' if compress else '')
        )
        uploaded_files['validation'] = upload_to_s3(
            val_file_actual,
            f"s3://{s3_bucket}/{s3_prefix}val.csv" + ('.gz' if compress else '')
        )
        uploaded_files['test'] = upload_to_s3(
            test_file_actual,
            f"s3://{s3_bucket}/{s3_prefix}test.csv" + ('.gz' if compress else '')
        )
        uploaded_files['metrics'] = upload_to_s3(
            metrics_file,
            f"s3://{s3_bucket}/{s3_prefix}metrics.json"
        )
        
        # Clean up temp files (use actual file paths)
        for f in [train_file_actual, val_file_actual, test_file_actual, metrics_file]:
            if os.path.exists(f):
                os.remove(f)
        
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
    
    if uploaded_files:
        print("\nUploaded files:")
        for split, uri in uploaded_files.items():
            print(f"  {split}: {uri}")
    
    return {
        'train_samples': len(train_df),
        'val_samples': len(val_df),
        'test_samples': len(test_df),
        'scale_pos_weight': train_metrics['scale_pos_weight'],
        'metrics': all_metrics,
        'uploaded_files': uploaded_files if uploaded_files else {
            'train': train_file,
            'validation': val_file,
            'test': test_file,
            'metrics': metrics_file
        }
    }


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Process training data for SageMaker XGBoost',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process TalkingData sample and save locally
  python scripts/process_training_data.py --data-source talkingdata --output ./processed/

  # Process full dataset and upload to S3
  python scripts/process_training_data.py \\
      --data-source talkingdata \\
      --output s3://bucket/fraud-detection/training/processed/ \\
      --use-smote \\
      --compress

  # Process FDB dataset with row limit
  python scripts/process_training_data.py \\
      --data-source fdb_ccfraud \\
      --output s3://bucket/training/ \\
      --nrows 50000
        """
    )
    
    parser.add_argument(
        '--data-source',
        type=str,
        default='talkingdata',
        choices=['talkingdata', 'synthetic', 'google_ads'] + [f'fdb_{i}' for i in range(1, 10)],
        help='Data source name (default: talkingdata)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output path (local directory or S3 URI like s3://bucket/path/)'
    )
    
    parser.add_argument(
        '--nrows',
        type=int,
        default=None,
        help='Limit number of rows to process (for testing)'
    )
    
    parser.add_argument(
        '--use-sample',
        action='store_true',
        default=True,
        help='For TalkingData, use sample file (default: True)'
    )
    
    parser.add_argument(
        '--no-use-sample',
        dest='use_sample',
        action='store_false',
        help='For TalkingData, use full file instead of sample'
    )
    
    parser.add_argument(
        '--use-chunking',
        action='store_true',
        help='Enable chunked processing for large datasets'
    )
    
    parser.add_argument(
        '--use-smote',
        action='store_true',
        help='Apply SMOTE oversampling to handle class imbalance'
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
        help='Random seed for reproducibility (default: 42)'
    )
    
    args = parser.parse_args()
    
    # Validate split sizes
    total_size = args.train_size + args.val_size + args.test_size
    if not np.isclose(total_size, 1.0, atol=1e-6):
        parser.error(f"Split sizes must sum to 1.0, got {total_size:.6f}")
    
    # Process data
    try:
        results = process_training_data(
            data_source=args.data_source,
            output_path=args.output,
            nrows=args.nrows,
            use_sample=args.use_sample,
            use_chunking=args.use_chunking,
            use_smote=args.use_smote,
            compress=args.compress,
            train_size=args.train_size,
            val_size=args.val_size,
            test_size=args.test_size,
            random_state=args.random_state
        )
        
        print("\n✅ Success!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

