#!/usr/bin/env python3
"""
Train XGBoost Model with SageMaker

Trains a baseline XGBoost model using SageMaker's built-in XGBoost algorithm.
Uses processed training data from S3 (created by process_training_data.py).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import boto3
import sagemaker
from sagemaker import Session
from sagemaker.inputs import TrainingInput
from sagemaker.xgboost.estimator import XGBoost

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_metrics_from_s3(s3_bucket: str, s3_prefix: str) -> Dict:
    """Load metrics.json from S3 to get scale_pos_weight"""
    s3_client = boto3.client('s3')
    if not s3_prefix.endswith('/'):
        s3_prefix += '/'
    metrics_key = f"{s3_prefix}metrics.json"
    try:
        print(f"Loading metrics from s3://{s3_bucket}/{metrics_key}...")
        response = s3_client.get_object(Bucket=s3_bucket, Key=metrics_key)
        metrics = json.loads(response['Body'].read().decode('utf-8'))
        print(f"  ✅ Scale pos weight: {metrics.get('scale_pos_weight', 1.0)}")
        return metrics
    except Exception as e:
        print(f"  ⚠️  Warning: Could not load metrics: {e}")
        return {'scale_pos_weight': 1.0}


def clamp_scale_pos_weight(value: float, min_value: float = 1.0) -> float:
    """
    Clamp scale_pos_weight to valid range for SageMaker XGBoost.
    
    SageMaker XGBoost requires scale_pos_weight >= 1.0.
    When fraud is the majority class, we use 1.0 (no weighting).
    
    Args:
        value: Calculated scale_pos_weight
        min_value: Minimum allowed value (default: 1.0)
    
    Returns:
        Clamped value >= min_value
    """
    return max(min_value, value) if value > 0 else min_value


def get_baseline_hyperparameters() -> Dict:
    """Get baseline hyperparameters for XGBoost"""
    return {
        'objective': 'binary:logistic',
                'num_round': 100,
        'max_depth': 6,
        'eta': 0.3,
                'min_child_weight': 1,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
                }


def train_baseline_model(
    s3_bucket: str,
    s3_prefix: str,
    sagemaker_role_arn: str,
    instance_type: str = 'ml.m5.xlarge',
    output_path: Optional[str] = None,
    job_name: Optional[str] = None,
    wait: bool = True
) -> Dict:
    """Train baseline XGBoost model using SageMaker"""
    print("=" * 70)
    print("SageMaker Baseline XGBoost Training")
    print("=" * 70)
    
    if not s3_prefix.endswith('/'):
        s3_prefix += '/'
    
    train_path = f"s3://{s3_bucket}/{s3_prefix}train.csv"
    val_path = f"s3://{s3_bucket}/{s3_prefix}val.csv"
    
    # Check for compressed files
    s3_client = boto3.client('s3')
    try:
        s3_client.head_object(Bucket=s3_bucket, Key=f"{s3_prefix}train.csv.gz")
        train_path += ".gz"
        val_path += ".gz"
        print(f"  Using compressed data files")
    except:
        pass
    
    print(f"Training data: {train_path}")
    print(f"Validation data: {val_path}")
    print()
    
    # Load metrics
    metrics = get_metrics_from_s3(s3_bucket, s3_prefix)
    scale_pos_weight = metrics.get('scale_pos_weight', 1.0)
    
    # Clamp to valid range (SageMaker requires >= 1.0)
    scale_pos_weight = clamp_scale_pos_weight(scale_pos_weight)
    if scale_pos_weight < 1.0:
        print(f"  ⚠️  Warning: scale_pos_weight ({scale_pos_weight:.6f}) < 1.0, clamping to 1.0")
    
    # Get hyperparameters
    hyperparameters = get_baseline_hyperparameters()
    
    print("Baseline Hyperparameters:")
    for key, value in hyperparameters.items():
        print(f"  {key}: {value}")
    print()
    
    if output_path is None:
        output_path = f"s3://{s3_bucket}/fraud-detection/models/xgboost/baseline/"
    
    print(f"Model output: {output_path}")
    print()
    
    # Initialize SageMaker session
    sess = sagemaker.Session()
    
    # Create XGBoost estimator
    print("Creating XGBoost estimator...")
    xgb_estimator = XGBoost(
        entry_point='scripts/xgboost_train.py',
        role=sagemaker_role_arn,
        instance_type=instance_type,
        instance_count=1,
        framework_version='1.7-1',
        hyperparameters=hyperparameters,
        output_path=output_path,
        base_job_name=job_name or 'fraudguard-xgboost-baseline',
        sagemaker_session=sess,
    )
    
    # Set up training inputs
    train_input = TrainingInput(s3_data=train_path, content_type='text/csv')
    val_input = TrainingInput(s3_data=val_path, content_type='text/csv')
    
    # Start training job
    print("Starting training job...")
    print(f"  Job name: {xgb_estimator._current_job_name}")
    print(f"  Instance: {instance_type}")
    print()
    
    xgb_estimator.fit(
        {'train': train_input, 'validation': val_input},
        wait=wait,
        logs=True
    )
    
    training_job_name = xgb_estimator.latest_training_job.name
    
    print()
    print("=" * 70)
    print("Training Complete!")
    print("=" * 70)
    if xgb_estimator.latest_training_job:
        training_job_name = xgb_estimator.latest_training_job.name
        print(f"Training job name: {training_job_name}")
        print(f"  Model artifact will be available after training completes")
        print(f"  Check status: aws sagemaker describe-training-job --training-job-name {training_job_name}")
    else:
        print("  Training job started (use --wait to see model artifact)")
    print(f"Model output path: {output_path}")
    
    if wait:
        print("\nTraining Metrics:")
        training_job = sess.sagemaker_client.describe_training_job(
            TrainingJobName=training_job_name
        )
        final_metrics = training_job.get('FinalMetricDataList', [])
        for metric in final_metrics:
            metric_name = metric.get('MetricName', '')
            metric_value = metric.get('Value', 0)
            if 'validation' in metric_name.lower() or 'train' in metric_name.lower():
                print(f"  {metric_name}: {metric_value:.6f}")
    
    return {
        'training_job_name': training_job_name,
        'model_artifact': xgb_estimator.model_data,
        'model_output_path': output_path,
        'hyperparameters': hyperparameters,
        'metrics': metrics,
        'estimator': xgb_estimator
    }


def get_stack_outputs(stack_name: str) -> Dict[str, str]:
    """Get CloudFormation stack outputs"""
    cf_client = boto3.client('cloudformation')
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = {}
        for output in response['Stacks'][0].get('Outputs', []):
            outputs[output['OutputKey']] = output['OutputValue']
        return outputs
    except Exception as e:
        print(f"  ⚠️  Warning: Could not get stack outputs: {e}")
        return {}


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Train baseline XGBoost model with SageMaker'
    )
    
    parser.add_argument('--s3-bucket', type=str, default=None,
                       help='S3 bucket name (or use S3_BUCKET env var)')
    parser.add_argument('--s3-prefix', type=str,
                       default='fraud-detection/training/processed/',
                       help='S3 prefix for training data')
    parser.add_argument('--sagemaker-role-arn', type=str, default=None,
                       help='SageMaker execution role ARN (or use SAGEMAKER_ROLE_ARN env var)')
    parser.add_argument('--stack-name', type=str, default=None,
                       help='CloudFormation stack name (auto-detects resources)')
    parser.add_argument('--instance-type', type=str, default='ml.m5.xlarge',
                       help='SageMaker training instance type')
    parser.add_argument('--output-path', type=str, default=None,
                       help='S3 path for model artifacts')
    parser.add_argument('--job-name', type=str, default=None,
                       help='Training job name')
    parser.add_argument('--no-wait', action='store_true',
                       help='Do not wait for training to complete')
    
    args = parser.parse_args()
    
    # Get parameters
    s3_bucket = args.s3_bucket or os.getenv('S3_BUCKET')
    sagemaker_role_arn = args.sagemaker_role_arn or os.getenv('SAGEMAKER_ROLE_ARN')
    
    if args.stack_name:
        stack_outputs = get_stack_outputs(args.stack_name)
        if not s3_bucket:
            s3_bucket = stack_outputs.get('DataBucketName')
        if not sagemaker_role_arn:
            account_id = boto3.client('sts').get_caller_identity()['Account']
            sagemaker_role_arn = f"arn:aws:iam::{account_id}:role/{args.stack_name}-sagemaker-execution-role"
    
    if not s3_bucket:
        parser.error("S3 bucket is required")
    if not sagemaker_role_arn:
        parser.error("SageMaker role ARN is required")
    
    try:
        results = train_baseline_model(
            s3_bucket=s3_bucket,
            s3_prefix=args.s3_prefix,
            sagemaker_role_arn=sagemaker_role_arn,
            instance_type=args.instance_type,
            output_path=args.output_path,
            job_name=args.job_name,
            wait=not args.no_wait
        )
        
        print("\n✅ Training job started successfully!")
        print(f"\nTo monitor: aws sagemaker describe-training-job --training-job-name {results['training_job_name']}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
