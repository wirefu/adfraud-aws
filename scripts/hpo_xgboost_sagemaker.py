#!/usr/bin/env python3
"""
Hyperparameter Optimization for XGBoost Model

Runs SageMaker hyperparameter tuning job to optimize XGBoost model performance.
Uses validation AUC as the objective metric.

Usage:
    python scripts/hpo_xgboost_sagemaker.py \
        --s3-bucket bucket-name \
        --s3-prefix fraud-detection/training/processed/ \
        --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole \
        --max-jobs 10 \
        --parallel-jobs 2
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import boto3
import sagemaker
from sagemaker.inputs import TrainingInput
from sagemaker.tuner import (
    ContinuousParameter,
    HyperparameterTuner,
    IntegerParameter,
)
from sagemaker.xgboost.estimator import XGBoost

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_metrics_from_s3(s3_bucket: str, s3_prefix: str) -> Dict:
    """
    Load metrics.json from S3 to get scale_pos_weight
    
    Args:
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for metrics file
    
    Returns:
        Dictionary with metrics including scale_pos_weight
    """
    s3_client = boto3.client('s3')
    
    if not s3_prefix.endswith('/'):
        s3_prefix += '/'
    
    metrics_key = f"{s3_prefix}metrics.json"
    
    try:
        response = s3_client.get_object(Bucket=s3_bucket, Key=metrics_key)
        metrics = json.loads(response['Body'].read().decode('utf-8'))
        
        scale_pos_weight = metrics.get('scale_pos_weight', 1.0)
        print(f"  ✅ Loaded metrics from s3://{s3_bucket}/{metrics_key}")
        print(f"  Scale pos weight: {scale_pos_weight:.4f}")
        
        return metrics
    except Exception as e:
        print(f"  ⚠️  Warning: Could not load metrics.json: {e}")
        print(f"  Using default scale_pos_weight: 1.0")
        return {'scale_pos_weight': 1.0}


def get_hyperparameter_ranges(
    scale_pos_weight: float = 1.0,
    use_research_ranges: bool = True
) -> Dict:
    """
    Define hyperparameter ranges for XGBoost tuning
    
    Based on research and best practices for imbalanced binary classification:
    - Focuses on parameters that affect class imbalance handling
    - Uses conservative ranges to prevent overfitting
    - Optimized for fraud detection use case
    
    Args:
        scale_pos_weight: Scale pos weight from metrics (used as fixed parameter)
        use_research_ranges: If True, use research-backed ranges for imbalanced data
    
    Returns:
        Dictionary of hyperparameter ranges for SageMaker tuner
    """
    if use_research_ranges:
        # Research-backed ranges for imbalanced binary classification
        ranges = {
            # Learning rate - smaller range for imbalanced data
            'eta': ContinuousParameter(0.01, 0.1),
            
            # Tree depth - conservative range to prevent overfitting
            'max_depth': IntegerParameter(3, 6),
            
            # Min child weight - higher range for robustness
            'min_child_weight': IntegerParameter(5, 10),
            
            # Subsample - moderate range
            'subsample': ContinuousParameter(0.7, 0.9),
            
            # Column sampling - moderate range
            'colsample_bytree': ContinuousParameter(0.5, 0.8),
            
            # Gamma - regularization parameter
            'gamma': ContinuousParameter(0, 2),
            
            # Number of boosting rounds - wide range
            'num_round': IntegerParameter(50, 200),
        }
    else:
        # Standard ranges from PRD
        ranges = {
            'num_round': IntegerParameter(50, 200),
            'max_depth': IntegerParameter(3, 10),
            'eta': ContinuousParameter(0.01, 0.3),
            'gamma': ContinuousParameter(0, 5),
            'min_child_weight': IntegerParameter(1, 10),
            'subsample': ContinuousParameter(0.5, 1.0),
            'colsample_bytree': ContinuousParameter(0.5, 1.0),
        }
    
    print("Hyperparameter ranges:")
    for param, value in ranges.items():
        if isinstance(value, IntegerParameter):
            print(f"  {param}: Integer [{value.min_value}, {value.max_value}]")
        elif isinstance(value, ContinuousParameter):
            print(f"  {param}: Continuous [{value.min_value}, {value.max_value}]")
    
    return ranges


def analyze_tuning_results(tuner: HyperparameterTuner, s3_bucket: str) -> None:
    """
    Analyze and display hyperparameter tuning results
    
    Args:
        tuner: HyperparameterTuner object after completion
        s3_bucket: S3 bucket name for saving results
    """
    sess = sagemaker.Session()
    
    # Get tuning job name
    tuning_job_name = tuner.latest_tuning_job.name
    
    # Get best training job
    best_training_job_name = tuner.best_training_job()
    print(f"Best Training Job: {best_training_job_name}")
    
    # Get best hyperparameters
    best_hyperparameters = tuner.best_estimator().hyperparameters()
    print("\nBest Hyperparameters:")
    for key, value in sorted(best_hyperparameters.items()):
        print(f"  {key}: {value}")
    
    # Get best objective metric value
    best_objective = tuner.best_training_job()['FinalHyperParameterTuningJobObjectiveMetric']['Value']
    print(f"\nBest Validation AUC: {best_objective:.6f}")
    
    # Get all training jobs and their metrics
    print("\n" + "=" * 70)
    print("All Training Jobs Summary")
    print("=" * 70)
    
    try:
        # Get tuning job details
        tuning_job_details = sess.sagemaker_client.describe_hyper_parameter_tuning_job(
            HyperParameterTuningJobName=tuning_job_name
        )
        
        # Get training job summaries
        training_job_summaries = tuning_job_details.get('TrainingJobSummaries', [])
        
        # Sort by final metric value (descending)
        training_job_summaries.sort(
            key=lambda x: float(x.get('FinalHyperParameterTuningJobObjectiveMetric', {}).get('Value', 0)),
            reverse=True
        )
        
        print(f"\nTotal Training Jobs: {len(training_job_summaries)}")
        print(f"\nTop 5 Models:")
        print("-" * 70)
        print(f"{'Rank':<6} {'Job Name':<50} {'Validation AUC':<15}")
        print("-" * 70)
        
        for idx, job_summary in enumerate(training_job_summaries[:5], 1):
            job_name = job_summary['TrainingJobName']
            metric = job_summary.get('FinalHyperParameterTuningJobObjectiveMetric', {})
            auc_value = float(metric.get('Value', 0))
            status = job_summary.get('TrainingJobStatus', 'Unknown')
            
            marker = "🏆" if idx == 1 else "  "
            print(f"{marker} {idx:<4} {job_name:<50} {auc_value:<15.6f} ({status})")
        
        # Calculate improvement metrics
        if len(training_job_summaries) > 1:
            best_auc = float(training_job_summaries[0].get('FinalHyperParameterTuningJobObjectiveMetric', {}).get('Value', 0))
            worst_auc = float(training_job_summaries[-1].get('FinalHyperParameterTuningJobObjectiveMetric', {}).get('Value', 0))
            avg_auc = sum(
                float(j.get('FinalHyperParameterTuningJobObjectiveMetric', {}).get('Value', 0))
                for j in training_job_summaries
            ) / len(training_job_summaries)
            
            print("\n" + "-" * 70)
            print(f"Best AUC:  {best_auc:.6f}")
            print(f"Worst AUC: {worst_auc:.6f}")
            print(f"Average AUC: {avg_auc:.6f}")
            print(f"Range: {best_auc - worst_auc:.6f}")
            print(f"Improvement over worst: {((best_auc - worst_auc) / worst_auc * 100):.2f}%")
        
    except Exception as e:
        print(f"  ⚠️  Could not retrieve detailed job summaries: {e}")
    
    # Save results to S3
    try:
        results = {
            'tuning_job_name': tuning_job_name,
            'best_training_job': best_training_job_name,
            'best_validation_auc': float(best_objective),
            'best_hyperparameters': {k: str(v) for k, v in best_hyperparameters.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        results_key = f"fraud-detection/models/xgboost/hpo/{tuning_job_name}/results.json"
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=results_key,
            Body=json.dumps(results, indent=2),
            ContentType='application/json'
        )
        print(f"\n✅ Results saved to: s3://{s3_bucket}/{results_key}")
    except Exception as e:
        print(f"\n⚠️  Could not save results to S3: {e}")
    
    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)
    print(f"1. Evaluate best model:")
    print(f"   python scripts/evaluate_model.py --training-job-name {best_training_job_name} --s3-bucket {s3_bucket}")
    print(f"\n2. Compare with baseline model:")
    print(f"   Review metrics to ensure improvement over baseline")
    print(f"\n3. Deploy best model:")
    print(f"   Use model artifact from training job: {best_training_job_name}")


def get_base_hyperparameters(scale_pos_weight: float = 1.0) -> Dict:
    """
    Get base hyperparameters (fixed, not tuned)
    
    Args:
        scale_pos_weight: Scale pos weight for class imbalance
    
    Returns:
        Dictionary of fixed hyperparameters
    """
    return {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'scale_pos_weight': scale_pos_weight,
        'verbosity': 1,
    }


def create_hpo_tuning_job(
    s3_bucket: str,
    s3_prefix: str,
    sagemaker_role_arn: str,
    max_jobs: int = 10,
    max_parallel_jobs: int = 2,
    instance_type: str = 'ml.m5.xlarge',
    output_path: Optional[str] = None,
    job_name: Optional[str] = None,
    wait: bool = True,
    use_research_ranges: bool = True
) -> HyperparameterTuner:
    """
    Create and run SageMaker hyperparameter tuning job
    
    Args:
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for training data
        sagemaker_role_arn: IAM role ARN for SageMaker
        max_jobs: Maximum number of training jobs to run
        max_parallel_jobs: Number of parallel training jobs
        instance_type: SageMaker instance type for training
        output_path: S3 path for model artifacts (default: s3://bucket/fraud-detection/models/xgboost/hpo/)
        job_name: Name for the tuning job (auto-generated if None)
        wait: If True, wait for tuning job to complete
        use_research_ranges: If True, use research-backed hyperparameter ranges
    
    Returns:
        HyperparameterTuner object
    """
    print("=" * 70)
    print("SageMaker Hyperparameter Optimization")
    print("=" * 70)
    print(f"S3 Bucket: {s3_bucket}")
    print(f"S3 Prefix: {s3_prefix}")
    print(f"Max Jobs: {max_jobs}")
    print(f"Parallel Jobs: {max_parallel_jobs}")
    print(f"Instance Type: {instance_type}")
    print()
    
    # Load metrics to get scale_pos_weight
    print("Loading metrics from S3...")
    metrics = get_metrics_from_s3(s3_bucket, s3_prefix)
    scale_pos_weight = metrics.get('scale_pos_weight', 1.0)
    print()
    
    # Set up S3 paths
    if not s3_prefix.endswith('/'):
        s3_prefix += '/'
    
    train_path = f"s3://{s3_bucket}/{s3_prefix}train.csv"
    val_path = f"s3://{s3_bucket}/{s3_prefix}val.csv"
    
    # Check if files are compressed
    s3_client = boto3.client('s3')
    try:
        s3_client.head_object(Bucket=s3_bucket, Key=f"{s3_prefix}train.csv.gz")
        train_path += ".gz"
        val_path += ".gz"
        print(f"  ✅ Using compressed data files")
    except:
        print(f"  ✅ Using uncompressed data files")
    
    print(f"  Train data: {train_path}")
    print(f"  Validation data: {val_path}")
    print()
    
    # Set output path
    if output_path is None:
        output_path = f"s3://{s3_bucket}/fraud-detection/models/xgboost/hpo/"
    
    # Generate job name if not provided
    if job_name is None:
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        job_name = f"fraudguard-xgboost-hpo-{timestamp}"
    
    print(f"Tuning Job Name: {job_name}")
    print(f"Output Path: {output_path}")
    print()
    
    # Create SageMaker session
    sess = sagemaker.Session()
    
    # Create base XGBoost estimator
    print("Creating XGBoost estimator...")
    base_hyperparameters = get_base_hyperparameters(scale_pos_weight)
    
    # Use script mode with custom training script for full hyperparameter support
    # This avoids algorithm mode validation issues (see docs/SCRIPT_MODE_VS_ALGORITHM_MODE_IMPACT.md)
    xgb_estimator = XGBoost(
        entry_point='xgboost_train.py',
        source_dir='scripts',
        role=sagemaker_role_arn,
        instance_type=instance_type,
        instance_count=1,  # Required for script mode
        framework_version='1.7-1',
        py_version='py3',
        hyperparameters=base_hyperparameters,
        output_path=output_path,
        sagemaker_session=sess
    )
    
    print("  ✅ Estimator created")
    print()
    
    # Define hyperparameter ranges
    print("Configuring hyperparameter ranges...")
    hyperparameter_ranges = get_hyperparameter_ranges(
        scale_pos_weight=scale_pos_weight,
        use_research_ranges=use_research_ranges
    )
    print("  ✅ Ranges configured")
    print()
    
    # Create hyperparameter tuner
    print("Creating hyperparameter tuner...")
    tuner = HyperparameterTuner(
        estimator=xgb_estimator,
        objective_metric_name='validation:auc',
        objective_type='Maximize',
        hyperparameter_ranges=hyperparameter_ranges,
        max_jobs=max_jobs,
        max_parallel_jobs=max_parallel_jobs,
        strategy='Bayesian',  # Bayesian optimization for efficient search
        early_stopping_type='Auto',
        base_tuning_job_name=job_name
    )
    
    print("  ✅ Tuner created")
    print()
    
    # Prepare training inputs
    train_input = TrainingInput(train_path, content_type='text/csv')
    val_input = TrainingInput(val_path, content_type='text/csv')
    
    # Start tuning job
    print("Starting hyperparameter tuning job...")
    print(f"  This will run {max_jobs} training jobs ({max_parallel_jobs} in parallel)")
    print(f"  Estimated time: {max_jobs // max_parallel_jobs * 30} - {max_jobs // max_parallel_jobs * 60} minutes")
    print()
    
    tuner.fit(
        {
            'train': train_input,
            'validation': val_input
        },
        wait=wait,
        logs=False  # Don't stream logs (too verbose for multiple jobs)
    )
    
    if wait:
        print()
        print("=" * 70)
        print("Tuning Job Complete!")
        print("=" * 70)
        
        # Analyze tuning results
        analyze_tuning_results(tuner, s3_bucket)
    else:
        print()
        print("=" * 70)
        print("Tuning Job Started!")
        print("=" * 70)
        print(f"Tuning Job Name: {job_name}")
        print(f"\nMonitor progress:")
        print(f"  AWS Console: https://console.aws.amazon.com/sagemaker/home#/hyper-tuning-jobs/{job_name}")
        print(f"\nCheck status:")
        print(f"  aws sagemaker describe-hyper-parameter-tuning-job --hyper-parameter-tuning-job-name {job_name}")
        print(f"\nAfter completion, get best model:")
        print(f"  python scripts/evaluate_model.py --training-job-name <best-job-name>")
    
    return tuner


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Run SageMaker hyperparameter optimization for XGBoost',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run HPO with default settings
  python scripts/hpo_xgboost_sagemaker.py \\
      --s3-bucket my-bucket \\
      --s3-prefix fraud-detection/training/processed/ \\
      --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole

  # Run HPO with custom job count and parallel jobs
  python scripts/hpo_xgboost_sagemaker.py \\
      --s3-bucket my-bucket \\
      --s3-prefix fraud-detection/training/processed/ \\
      --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole \\
      --max-jobs 20 \\
      --parallel-jobs 3

  # Run HPO asynchronously (don't wait for completion)
  python scripts/hpo_xgboost_sagemaker.py \\
      --s3-bucket my-bucket \\
      --s3-prefix fraud-detection/training/processed/ \\
      --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole \\
      --no-wait
        """
    )
    
    # S3 configuration
    parser.add_argument(
        '--s3-bucket',
        type=str,
        help='S3 bucket name for training data (or set S3_BUCKET env var)'
    )
    
    parser.add_argument(
        '--s3-prefix',
        type=str,
        default='fraud-detection/training/processed/',
        help='S3 prefix for training data (default: fraud-detection/training/processed/)'
    )
    
    # SageMaker configuration
    parser.add_argument(
        '--sagemaker-role-arn',
        type=str,
        help='SageMaker execution role ARN (or set SAGEMAKER_ROLE_ARN env var)'
    )
    
    parser.add_argument(
        '--stack-name',
        type=str,
        help='CloudFormation stack name (auto-detects S3 bucket and role if not provided)'
    )
    
    # HPO configuration
    parser.add_argument(
        '--max-jobs',
        type=int,
        default=10,
        help='Maximum number of training jobs to run (default: 10)'
    )
    
    parser.add_argument(
        '--parallel-jobs',
        type=int,
        default=2,
        help='Number of parallel training jobs (default: 2)'
    )
    
    parser.add_argument(
        '--instance-type',
        type=str,
        default='ml.m5.xlarge',
        help='SageMaker instance type for training (default: ml.m5.xlarge)'
    )
    
    parser.add_argument(
        '--output-path',
        type=str,
        help='S3 path for model artifacts (default: s3://bucket/fraud-detection/models/xgboost/hpo/)'
    )
    
    parser.add_argument(
        '--job-name',
        type=str,
        help='Name for the tuning job (auto-generated if not provided)'
    )
    
    parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Don\'t wait for tuning job to complete (run asynchronously)'
    )
    
    parser.add_argument(
        '--use-standard-ranges',
        action='store_true',
        help='Use standard hyperparameter ranges instead of research-backed ranges'
    )
    
    args = parser.parse_args()
    
    # Resolve S3 bucket
    s3_bucket = args.s3_bucket or os.getenv('S3_BUCKET')
    if not s3_bucket and args.stack_name:
        # Try to get from CloudFormation
        cf_client = boto3.client('cloudformation')
        try:
            stack = cf_client.describe_stacks(StackName=args.stack_name)
            outputs = {o['OutputKey']: o['OutputValue'] for o in stack['Stacks'][0].get('Outputs', [])}
            s3_bucket = outputs.get('DataBucketName')
            if s3_bucket:
                print(f"  ✅ Auto-detected S3 bucket from stack: {s3_bucket}")
        except Exception as e:
            print(f"  ⚠️  Could not get bucket from stack: {e}")
    
    if not s3_bucket:
        parser.error("S3 bucket must be provided via --s3-bucket, S3_BUCKET env var, or --stack-name")
    
    # Resolve SageMaker role
    sagemaker_role_arn = args.sagemaker_role_arn or os.getenv('SAGEMAKER_ROLE_ARN')
    if not sagemaker_role_arn and args.stack_name:
        # Try to get from CloudFormation
        cf_client = boto3.client('cloudformation')
        try:
            stack = cf_client.describe_stacks(StackName=args.stack_name)
            outputs = {o['OutputKey']: o['OutputValue'] for o in stack['Stacks'][0].get('Outputs', [])}
            sagemaker_role_arn = outputs.get('SageMakerRoleArn')
            if sagemaker_role_arn:
                print(f"  ✅ Auto-detected SageMaker role from stack: {sagemaker_role_arn}")
        except Exception as e:
            print(f"  ⚠️  Could not get role from stack: {e}")
    
    if not sagemaker_role_arn:
        parser.error("SageMaker role ARN must be provided via --sagemaker-role-arn, SAGEMAKER_ROLE_ARN env var, or --stack-name")
    
    # Validate parallel jobs
    if args.parallel_jobs > args.max_jobs:
        parser.error(f"Parallel jobs ({args.parallel_jobs}) cannot exceed max jobs ({args.max_jobs})")
    
    # Run HPO
    try:
        tuner = create_hpo_tuning_job(
            s3_bucket=s3_bucket,
            s3_prefix=args.s3_prefix,
            sagemaker_role_arn=sagemaker_role_arn,
            max_jobs=args.max_jobs,
            max_parallel_jobs=args.parallel_jobs,
            instance_type=args.instance_type,
            output_path=args.output_path,
            job_name=args.job_name,
            wait=not args.no_wait,
            use_research_ranges=not args.use_standard_ranges
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

