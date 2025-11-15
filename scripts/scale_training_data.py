#!/usr/bin/env python3
"""
Scale Training Data - Process larger dataset for improved model performance

This script processes a larger subset of the TalkingData dataset to improve
model training. It supports incremental scaling (100k, 500k, 1M, etc.)

Usage:
    # Process 100k records
    python scripts/scale_training_data.py --nrows 100000 --output s3://bucket/path/

    # Process 500k records with SMOTE
    python scripts/scale_training_data.py --nrows 500000 --use-smote --compress

    # Process 1M records (full processing)
    python scripts/scale_training_data.py --nrows 1000000 --compress
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, Dict
import boto3
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.process_training_data import process_training_data, upload_to_s3


def scale_training_data(
    nrows: int = 100000,
    output_path: Optional[str] = None,
    use_smote: bool = False,
    compress: bool = True,
    upload_to_s3_flag: bool = True,
    bucket: Optional[str] = None
) -> Dict:
    """
    Scale training data by processing larger dataset.
    
    Args:
        nrows: Number of rows to process (100k, 500k, 1M, etc.)
        output_path: Local output path or S3 URI
        use_smote: Apply SMOTE oversampling
        compress: Compress output files
        upload_to_s3_flag: Upload to S3 after processing
        bucket: S3 bucket name (if not in output_path)
    
    Returns:
        Dictionary with processing results
    """
    print("=" * 70)
    print("SCALING TRAINING DATA")
    print("=" * 70)
    print(f"Target: {nrows:,} records")
    print(f"Source: TalkingData full dataset (train.csv)")
    print(f"SMOTE: {'Enabled' if use_smote else 'Disabled'}")
    print(f"Compression: {'Enabled' if compress else 'Disabled'}")
    print()
    
    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if upload_to_s3_flag:
            if bucket is None:
                # Try to get bucket from Terraform output
                try:
                    import subprocess
                    result = subprocess.run(
                        ['terraform', 'output', '-raw', 's3_bucket_name'],
                        cwd=project_root / 'terraform',
                        capture_output=True,
                        text=True
                    )
                    bucket = result.stdout.strip()
                except:
                    bucket = "fraudguard-ai-data-971422717446"
            
            output_path = f"s3://{bucket}/fraud-detection/training/processed/scaled-{nrows//1000}k-{timestamp}/"
        else:
            output_path = f"./data/training/scaled-{nrows//1000}k-{timestamp}/"
    
    print(f"Output: {output_path}")
    print()
    
    # Process the data
    print("Starting data processing...")
    print("(This may take 10-30 minutes depending on dataset size)")
    print()
    
    results = process_training_data(
        data_source="talkingdata",
        output_path=output_path,
        nrows=nrows,
        use_sample=False,  # Use full dataset, not sample
        use_chunking=True,  # Enable chunking for large files
        use_smote=use_smote,
        compress=compress,
        train_size=0.7,
        val_size=0.15,
        test_size=0.15,
        random_state=42
    )
    
    print()
    print("=" * 70)
    print("✅ SCALING COMPLETE")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  • Training samples: {results.get('train_samples', 0):,}")
    print(f"  • Validation samples: {results.get('val_samples', 0):,}")
    print(f"  • Test samples: {results.get('test_samples', 0):,}")
    print(f"  • Total processed: {results.get('total_samples', 0):,}")
    print()
    
    if 'output_files' in results:
        print("Output files:")
        for file_type, file_path in results['output_files'].items():
            print(f"  • {file_type}: {file_path}")
    
    print()
    print("Next Steps:")
    print("  1. Verify processed data quality")
    print("  2. Train model with new dataset")
    print("  3. Compare performance with previous model")
    print("  4. Deploy if performance improved")
    print()
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Scale training data by processing larger dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process 100k records
  python scripts/scale_training_data.py --nrows 100000

  # Process 500k records with SMOTE
  python scripts/scale_training_data.py --nrows 500000 --use-smote

  # Process 1M records, save locally
  python scripts/scale_training_data.py --nrows 1000000 --no-upload

  # Process 2M records with compression
  python scripts/scale_training_data.py --nrows 2000000 --compress
        """
    )
    
    parser.add_argument(
        '--nrows',
        type=int,
        default=100000,
        help='Number of rows to process (default: 100000). Recommended: 100k, 500k, 1M, 2M'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path (local directory or S3 URI). Default: auto-generated S3 path'
    )
    
    parser.add_argument(
        '--use-smote',
        action='store_true',
        help='Apply SMOTE oversampling for class balance'
    )
    
    parser.add_argument(
        '--compress',
        action='store_true',
        default=True,
        help='Compress output files with gzip (default: True)'
    )
    
    parser.add_argument(
        '--no-compress',
        dest='compress',
        action='store_false',
        help='Disable compression'
    )
    
    parser.add_argument(
        '--no-upload',
        dest='upload_to_s3',
        action='store_false',
        default=True,
        help='Save locally instead of uploading to S3'
    )
    
    parser.add_argument(
        '--bucket',
        type=str,
        default=None,
        help='S3 bucket name (if not specified in --output)'
    )
    
    args = parser.parse_args()
    
    try:
        results = scale_training_data(
            nrows=args.nrows,
            output_path=args.output,
            use_smote=args.use_smote,
            compress=args.compress,
            upload_to_s3_flag=args.upload_to_s3,
            bucket=args.bucket
        )
        
        print("✅ Success!")
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

