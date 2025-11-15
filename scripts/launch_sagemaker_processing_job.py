#!/usr/bin/env python3
"""
Launch SageMaker Processing Job for Training Data Processing

This script creates and launches a SageMaker Processing Job to process
training data in AWS (Option B: AWS-Native Processing).

Usage:
    python scripts/launch_sagemaker_processing_job.py \
        --s3-bucket bucket-name \
        --input-s3-path s3://bucket/fraud-detection/training/raw/ \
        --output-s3-path s3://bucket/fraud-detection/training/processed/ \
        --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole \
        --data-source talkingdata \
        --instance-type ml.m5.xlarge
"""

import argparse
import json
import os
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
import sagemaker
from sagemaker.processing import ProcessingInput, ProcessingOutput, ScriptProcessor
from sagemaker.sklearn.processing import SKLearnProcessor

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_stack_outputs(stack_name: str) -> dict:
    """
    Get CloudFormation stack outputs
    
    Args:
        stack_name: CloudFormation stack name
    
    Returns:
        Dictionary of stack outputs
    """
    cf_client = boto3.client('cloudformation')
    
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = {}
        for output in response['Stacks'][0].get('Outputs', []):
            outputs[output['OutputKey']] = output['OutputValue']
        return outputs
    except Exception as e:
        print(f"  ⚠️  Could not get stack outputs: {e}")
        return {}


def package_code_for_processing(s3_bucket: str, s3_prefix: str = 'fraud-detection/processing/code/') -> str:
    """
    Package training modules and upload to S3 for Processing Job
    
    Args:
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for code package
    
    Returns:
        S3 URI of the code package
    """
    print("Packaging code for SageMaker Processing...")
    
    s3_client = boto3.client('s3')
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        code_dir = Path(temp_dir) / 'code'
        code_dir.mkdir()
        
        # Copy training modules
        training_dir = code_dir / 'training'
        training_dir.mkdir()
        
        # Copy training package files
        source_training = Path(__file__).parent.parent / 'training'
        for file in ['__init__.py', 'feature_engineering.py', 'data_loader.py', 
                     'preprocessing.py', 'data_splitting.py']:
            source_file = source_training / file
            if source_file.exists():
                shutil.copy2(source_file, training_dir / file)
                print(f"  ✅ Copied {file}")
        
        # Copy processing script
        processing_script = Path(__file__).parent / 'process_training_data_sagemaker.py'
        shutil.copy2(processing_script, code_dir / 'process_training_data_sagemaker.py')
        print(f"  ✅ Copied processing script")
        
        # Copy process_training_data.py (for helper functions)
        helper_script = Path(__file__).parent / 'process_training_data.py'
        scripts_dir = code_dir / 'scripts'
        scripts_dir.mkdir()
        shutil.copy2(helper_script, scripts_dir / 'process_training_data.py')
        print(f"  ✅ Copied helper script")
        
        # Create requirements.txt
        requirements = [
            'pandas>=2.0.0',
            'numpy>=1.24.0',
            'scikit-learn>=1.3.0',
            'imbalanced-learn>=0.11.0',
            'boto3>=1.34.0',
        ]
        
        requirements_file = code_dir / 'requirements.txt'
        with open(requirements_file, 'w') as f:
            f.write('\n'.join(requirements))
        print(f"  ✅ Created requirements.txt")
        
        # Create tar.gz archive
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        tar_filename = f'processing-code-{timestamp}.tar.gz'
        tar_path = Path(temp_dir) / tar_filename
        
        with tarfile.open(tar_path, 'w:gz') as tar:
            tar.add(code_dir, arcname='code')
        
        print(f"  ✅ Created archive: {tar_path.name} ({tar_path.stat().st_size / 1024 / 1024:.2f} MB)")
        
        # Upload to S3
        if not s3_prefix.endswith('/'):
            s3_prefix += '/'
        
        s3_key = f"{s3_prefix}{tar_filename}"
        s3_uri = f"s3://{s3_bucket}/{s3_key}"
        
        print(f"  Uploading to {s3_uri}...")
        s3_client.upload_file(str(tar_path), s3_bucket, s3_key)
        print(f"  ✅ Uploaded to {s3_uri}")
        
        return s3_uri


def launch_processing_job(
    s3_bucket: str,
    input_s3_path: str,
    output_s3_path: str,
    sagemaker_role_arn: str,
    data_source: str = 'talkingdata',
    instance_type: str = 'ml.m5.xlarge',
    instance_count: int = 1,
    nrows: Optional[int] = None,
    use_smote: bool = False,
    compress: bool = False,
    job_name: Optional[str] = None,
    wait: bool = True
) -> str:
    """
    Launch SageMaker Processing Job
    
    Args:
        s3_bucket: S3 bucket name
        input_s3_path: S3 path to raw input data
        output_s3_path: S3 path for processed output data
        sagemaker_role_arn: SageMaker execution role ARN
        data_source: Data source name
        instance_type: Processing instance type
        instance_count: Number of processing instances
        nrows: Limit number of rows (for testing)
        use_smote: Apply SMOTE oversampling
        compress: Compress output files
        job_name: Processing job name (auto-generated if None)
        wait: If True, wait for job to complete
    
    Returns:
        Processing job name
    """
    print("=" * 70)
    print("Launching SageMaker Processing Job")
    print("=" * 70)
    print(f"Input: {input_s3_path}")
    print(f"Output: {output_s3_path}")
    print(f"Instance: {instance_type} (x{instance_count})")
    print()
    
    # Package code
    code_s3_uri = package_code_for_processing(s3_bucket)
    print()
    
    # Create SKLearn processor
    sess = sagemaker.Session()
    
    processor = SKLearnProcessor(
        framework_version='1.2-1',
        role=sagemaker_role_arn,
        instance_type=instance_type,
        instance_count=instance_count,
        sagemaker_session=sess
    )
    
    # Generate job name
    if not job_name:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        job_name = f"fraudguard-data-processing-{timestamp}"
    
    print(f"Processing Job Name: {job_name}")
    print()
    
    # Prepare processing inputs
    # Input 1: Raw data from S3
    processing_inputs = [
        ProcessingInput(
            source=input_s3_path,
            destination='/opt/ml/processing/input/data',
            input_name='raw_data'
        ),
        # Input 2: Code package
        ProcessingInput(
            source=code_s3_uri,
            destination='/opt/ml/processing/input/code',
            input_name='code'
        )
    ]
    
    # Prepare processing outputs
    processing_outputs = [
        ProcessingOutput(
            source='/opt/ml/processing/output',
            destination=output_s3_path,
            output_name='processed_data'
        )
    ]
    
    # Prepare script arguments
    script_args = [
        '--input-data-source', data_source,
        '--input-s3-path', input_s3_path,
        '--output-s3-path', output_s3_path,
    ]
    
    if nrows:
        script_args.extend(['--nrows', str(nrows)])
    
    if use_smote:
        script_args.append('--use-smote')
    
    if compress:
        script_args.append('--compress')
    
    # Launch processing job
    print("Launching processing job...")
    print(f"  This may take 30-60 minutes depending on data size")
    print()
    
    processor.run(
        code='process_training_data_sagemaker.py',
        inputs=processing_inputs,
        outputs=processing_outputs,
        arguments=script_args,
        job_name=job_name,
        wait=wait,
        logs=False  # Don't stream logs (too verbose)
    )
    
    if wait:
        print()
        print("=" * 70)
        print("Processing Job Complete!")
        print("=" * 70)
        print(f"Job Name: {job_name}")
        print(f"\nProcessed data available at:")
        print(f"  {output_s3_path}")
        print(f"\nNext steps:")
        print(f"  1. Verify processed data in S3")
        print(f"  2. Run baseline training:")
        print(f"     python scripts/train_xgboost_sagemaker.py \\")
        print(f"         --s3-bucket {s3_bucket} \\")
        print(f"         --s3-prefix fraud-detection/training/processed/")
    else:
        print()
        print("=" * 70)
        print("Processing Job Started!")
        print("=" * 70)
        print(f"Job Name: {job_name}")
        print(f"\nMonitor progress:")
        print(f"  AWS Console: https://console.aws.amazon.com/sagemaker/home#/processing-jobs/{job_name}")
        print(f"\nCheck status:")
        print(f"  aws sagemaker describe-processing-job --processing-job-name {job_name}")
    
    return job_name


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Launch SageMaker Processing Job for training data processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch processing job with auto-detection
  python scripts/launch_sagemaker_processing_job.py --stack-name fraudguard-ai-dev

  # Launch with explicit parameters
  python scripts/launch_sagemaker_processing_job.py \\
      --s3-bucket bucket-name \\
      --input-s3-path s3://bucket/fraud-detection/training/raw/ \\
      --output-s3-path s3://bucket/fraud-detection/training/processed/ \\
      --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole \\
      --instance-type ml.m5.2xlarge

  # Launch with SMOTE and compression
  python scripts/launch_sagemaker_processing_job.py \\
      --stack-name fraudguard-ai-dev \\
      --use-smote \\
      --compress \\
      --instance-type ml.m5.2xlarge
        """
    )
    
    parser.add_argument(
        '--s3-bucket',
        type=str,
        default=None,
        help='S3 bucket name (or use --stack-name for auto-detection)'
    )
    
    parser.add_argument(
        '--input-s3-path',
        type=str,
        default=None,
        help='S3 path to raw input data (default: s3://bucket/fraud-detection/training/raw/)'
    )
    
    parser.add_argument(
        '--output-s3-path',
        type=str,
        default=None,
        help='S3 path for processed output data (default: s3://bucket/fraud-detection/training/processed/)'
    )
    
    parser.add_argument(
        '--sagemaker-role-arn',
        type=str,
        default=None,
        help='SageMaker execution role ARN (or use --stack-name for auto-detection)'
    )
    
    parser.add_argument(
        '--stack-name',
        type=str,
        default=None,
        help='CloudFormation stack name for auto-detection of resources'
    )
    
    parser.add_argument(
        '--data-source',
        type=str,
        default='talkingdata',
        help='Data source name (default: talkingdata)'
    )
    
    parser.add_argument(
        '--instance-type',
        type=str,
        default='ml.m5.xlarge',
        help='Processing instance type (default: ml.m5.xlarge)'
    )
    
    parser.add_argument(
        '--instance-count',
        type=int,
        default=1,
        help='Number of processing instances (default: 1)'
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
        '--job-name',
        type=str,
        default=None,
        help='Processing job name (auto-generated if not provided)'
    )
    
    parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Do not wait for job to complete (run asynchronously)'
    )
    
    args = parser.parse_args()
    
    # Auto-detect from stack if provided
    if args.stack_name:
        print(f"Auto-detecting resources from stack: {args.stack_name}")
        outputs = get_stack_outputs(args.stack_name)
        
        s3_bucket = args.s3_bucket or outputs.get('DataBucketName')
        sagemaker_role_arn = args.sagemaker_role_arn or outputs.get('SageMakerExecutionRoleArn')
        
        if not s3_bucket:
            # Try Terraform output
            import subprocess
            try:
                result = subprocess.run(
                    ['terraform', 'output', '-raw', 'data_bucket_name'],
                    cwd=Path(__file__).parent.parent / 'terraform',
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    s3_bucket = result.stdout.strip()
            except:
                pass
        
        if not sagemaker_role_arn:
            # Try Terraform output
            import subprocess
            try:
                result = subprocess.run(
                    ['terraform', 'output', '-raw', 'sagemaker_execution_role_arn'],
                    cwd=Path(__file__).parent.parent / 'terraform',
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    sagemaker_role_arn = result.stdout.strip()
            except:
                pass
        
        print(f"  S3 Bucket: {s3_bucket}")
        print(f"  SageMaker Role: {sagemaker_role_arn}")
        print()
    else:
        s3_bucket = args.s3_bucket or os.getenv('S3_BUCKET')
        sagemaker_role_arn = args.sagemaker_role_arn or os.getenv('SAGEMAKER_ROLE_ARN')
    
    if not s3_bucket:
        parser.error("S3 bucket is required (use --s3-bucket, --stack-name, or S3_BUCKET env var)")
    
    if not sagemaker_role_arn:
        parser.error("SageMaker role ARN is required (use --sagemaker-role-arn, --stack-name, or SAGEMAKER_ROLE_ARN env var)")
    
    # Set default paths if not provided
    if not args.input_s3_path:
        args.input_s3_path = f"s3://{s3_bucket}/fraud-detection/training/raw/"
    
    if not args.output_s3_path:
        args.output_s3_path = f"s3://{s3_bucket}/fraud-detection/training/processed/"
    
    try:
        job_name = launch_processing_job(
            s3_bucket=s3_bucket,
            input_s3_path=args.input_s3_path,
            output_s3_path=args.output_s3_path,
            sagemaker_role_arn=sagemaker_role_arn,
            data_source=args.data_source,
            instance_type=args.instance_type,
            instance_count=args.instance_count,
            nrows=args.nrows,
            use_smote=args.use_smote,
            compress=args.compress,
            job_name=args.job_name,
            wait=not args.no_wait
        )
        
        print("\n✅ Processing job launched successfully!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

