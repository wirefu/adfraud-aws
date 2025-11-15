#!/usr/bin/env python3
"""
Process Sample Data for Training

A focused script to process training data for quick testing and development.
Uses the full dataset (not sample files) for processing.

Usage:
    # Process TalkingData full dataset
    python scripts/process_sample_data.py --data-source talkingdata --output ./processed/
    
    # Process with SMOTE and compression
    python scripts/process_sample_data.py --data-source talkingdata --use-smote --compress --output ./processed/
    
    # Process with row limit for quick testing
    python scripts/process_sample_data.py --data-source talkingdata --nrows 10000 --output ./processed/
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
    upload_to_s3
)


def process_sample_data(
    data_source: str = "talkingdata",
    output_path: str = None,
    nrows: Optional[int] = None,
    use_smote: bool = False,
    compress: bool = False,
    train_size: float = 0.7,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42
) -> Dict:
    """
    Process sample training data end-to-end
    
    Args:
        data_source: Data source name ("talkingdata", "synthetic")
        output_path: Output path (S3 URI or local directory)
        nrows: Limit number of rows (for testing)
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
    print("Processing Training Data")
    print("=" * 70)
    print(f"Data source: {data_source}")
    print(f"Output: {output_path}")
    if nrows:
        print(f"Row limit: {nrows:,}")
    print()
    
    # Step 1: Load and engineer features
    print("Step 1: Loading and engineering features...")
    try:
        splits = load_and_engineer_features(
            data_source=data_source,
            use_sample=False,  # Use full dataset
            nrows=nrows,
            use_chunking=True,  # Enable chunking for large datasets
            preprocess=True,
            split_data=True,
            train_size=train_size,
            val_size=val_size,
            test_size=test_size,
            stratify=True,
            random_state=random_state
        )
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("\n💡 Tip: Ensure data files are available. For TalkingData, download using:")
        print("   python scripts/download_talkingdata_kaggle.py")
        sys.exit(1)
    
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
    
    print(f"  ✅ Formatted: {len(FEATURE_NAMES)} features + label")
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
            output_dir = Path('processed')
            output_dir.mkdir(exist_ok=True)
        
        train_file = str(output_dir / 'train.csv')
        val_file = str(output_dir / 'val.csv')
        test_file = str(output_dir / 'test.csv')
        metrics_file = str(output_dir / 'metrics.json')
    
    # Save CSV files
    save_to_csv_sagemaker_format(train_file, train_sagemaker, compress=compress)
    save_to_csv_sagemaker_format(val_file, val_sagemaker, compress=compress)
    save_to_csv_sagemaker_format(test_file, test_sagemaker, compress=compress)
    
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
        
        # Upload files
        uploaded_files['train'] = upload_to_s3(
            train_file,
            f"s3://{s3_bucket}/{s3_prefix}train.csv" + ('.gz' if compress else '')
        )
        uploaded_files['validation'] = upload_to_s3(
            val_file,
            f"s3://{s3_bucket}/{s3_prefix}val.csv" + ('.gz' if compress else '')
        )
        uploaded_files['test'] = upload_to_s3(
            test_file,
            f"s3://{s3_bucket}/{s3_prefix}test.csv" + ('.gz' if compress else '')
        )
        uploaded_files['metrics'] = upload_to_s3(
            metrics_file,
            f"s3://{s3_bucket}/{s3_prefix}metrics.json"
        )
        
        # Clean up temp files
        for f in [train_file, val_file, test_file, metrics_file]:
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
    else:
        print("\nSaved files:")
        print(f"  train: {train_file}")
        print(f"  validation: {val_file}")
        print(f"  test: {test_file}")
        print(f"  metrics: {metrics_file}")
    
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
        description='Process training data for model training',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process TalkingData full dataset
  python scripts/process_sample_data.py --data-source talkingdata --output ./processed/

  # Process with SMOTE and compression
  python scripts/process_sample_data.py --data-source talkingdata --use-smote --compress --output ./processed/

  # Process with row limit for quick testing
  python scripts/process_sample_data.py --data-source talkingdata --nrows 10000 --output ./processed/
        """
    )
    
    parser.add_argument(
        '--data-source',
        type=str,
        default='talkingdata',
        choices=['talkingdata', 'synthetic'],
        help='Data source name (default: talkingdata). Note: synthetic requires existing data files.'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='./processed/',
        help='Output path (local directory or S3 URI like s3://bucket/path/)'
    )
    
    parser.add_argument(
        '--nrows',
        type=int,
        default=None,
        help='Limit number of rows to process (for testing). Default: all available'
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
        results = process_sample_data(
            data_source=args.data_source,
            output_path=args.output,
            nrows=args.nrows,
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

