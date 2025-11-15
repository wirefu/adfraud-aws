#!/usr/bin/env python3
"""
Evaluate Trained XGBoost Model

Evaluates a trained SageMaker XGBoost model on validation/test data.
Calculates performance metrics: ROC AUC, F1 Score, Cohen's Kappa, Balanced Accuracy.

Usage:
    python scripts/evaluate_model.py \
        --training-job-name fraudguard-xgboost-baseline-2024-11-13-123456 \
        --s3-bucket bucket-name \
        --s3-prefix fraud-detection/training/processed/
"""

import argparse
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import boto3
import numpy as np
import pandas as pd
import sagemaker
import xgboost as xgb
from sagemaker.predictor import Predictor
from sklearn.metrics import (
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
    classification_report
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.feature_engineering import FEATURE_NAMES


def load_test_data_from_s3(s3_bucket: str, s3_prefix: str, use_compressed: bool = False) -> tuple:
    """
    Load test data from S3
    
    Args:
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for test data
        use_compressed: If True, load compressed file
    
    Returns:
        Tuple of (X_test, y_test) as DataFrames
    """
    s3_client = boto3.client('s3')
    
    if not s3_prefix.endswith('/'):
        s3_prefix += '/'
    
    test_key = f"{s3_prefix}test.csv"
    if use_compressed:
        test_key += ".gz"
    
    print(f"Loading test data from s3://{s3_bucket}/{test_key}...")
    
    try:
        response = s3_client.get_object(Bucket=s3_bucket, Key=test_key)
        df = pd.read_csv(
            response['Body'],
            header=None,
            compression='gzip' if use_compressed else None
        )
        
        # Last column is label, rest are features
        X_test = df.iloc[:, :-1]
        y_test = df.iloc[:, -1]
        
        print(f"  ✅ Loaded {len(df):,} samples with {X_test.shape[1]} features")
        return X_test, y_test
    except Exception as e:
        print(f"  ❌ Error loading test data: {e}")
        raise


def get_model_from_training_job(training_job_name: str) -> Predictor:
    """
    Get model predictor from training job
    
    Args:
        training_job_name: Name of the training job
    
    Returns:
        SageMaker Predictor object
    """
    sess = sagemaker.Session()
    
    # Get training job details
    training_job = sess.sagemaker_client.describe_training_job(
        TrainingJobName=training_job_name
    )
    
    model_artifact = training_job['ModelArtifacts']['S3ModelArtifacts']
    print(f"Model artifact: {model_artifact}")
    
    # Create model
    from sagemaker.xgboost.model import XGBoostModel
    
    model = XGBoostModel(
        model_data=model_artifact,
        role=training_job['RoleArn'],
        framework_version='1.7-1',
        sagemaker_session=sess
    )
    
    # Deploy model to endpoint for evaluation
    endpoint_name = f"{training_job_name}-eval"
    print(f"Deploying model to endpoint: {endpoint_name}...")
    
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type='ml.t2.medium',
        endpoint_name=endpoint_name,
        serializer=sagemaker.serializers.CSVSerializer(),
        deserializer=sagemaker.deserializers.CSVDeserializer()
    )
    
    print(f"  ✅ Model deployed to endpoint: {endpoint_name}")
    return predictor, endpoint_name


def predict_batch(predictor: Predictor, X_test: pd.DataFrame, batch_size: int = 100) -> np.ndarray:
    """
    Make predictions in batches
    
    Args:
        predictor: SageMaker predictor
        X_test: Test features
        batch_size: Batch size for predictions
    
    Returns:
        Array of predictions
    """
    predictions = []
    total_batches = (len(X_test) + batch_size - 1) // batch_size
    
    print(f"Making predictions in {total_batches} batches...")
    
    for i in range(0, len(X_test), batch_size):
        batch = X_test.iloc[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        # Convert to CSV format (no headers)
        batch_csv = batch.to_csv(header=False, index=False)
        
        try:
            response = predictor.predict(batch_csv)
            # Response is a list of predictions
            if isinstance(response, list):
                batch_preds = [float(p) for p in response]
            else:
                batch_preds = [float(response)]
            
            predictions.extend(batch_preds)
            
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"  Processed {batch_num}/{total_batches} batches ({min(i+batch_size, len(X_test)):,}/{len(X_test):,} samples)")
        except Exception as e:
            print(f"  ⚠️  Error in batch {batch_num}: {e}")
            # Fill with zeros for failed batch
            predictions.extend([0.0] * len(batch))
    
    return np.array(predictions)


def extract_feature_importance(training_job_name: str, s3_bucket: str) -> Dict:
    """
    Extract feature importance from trained XGBoost model
    
    Args:
        training_job_name: Name of the training job
        s3_bucket: S3 bucket name
    
    Returns:
        Dictionary with feature importance scores
    """
    print("Extracting feature importance from model...")
    
    sess = sagemaker.Session()
    
    # Get training job details
    training_job = sess.sagemaker_client.describe_training_job(
        TrainingJobName=training_job_name
    )
    
    model_artifact = training_job['ModelArtifacts']['S3ModelArtifacts']
    print(f"  Model artifact: {model_artifact}")
    
    # Download and extract model
    s3_client = boto3.client('s3')
    
    # Parse S3 path
    s3_path = model_artifact.replace('s3://', '')
    bucket, key = s3_path.split('/', 1)
    
    # Download model to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        model_tar = os.path.join(temp_dir, 'model.tar.gz')
        print(f"  Downloading model to {model_tar}...")
        
        s3_client.download_file(bucket, key, model_tar)
        
        # Extract model
        model_dir = os.path.join(temp_dir, 'model')
        os.makedirs(model_dir, exist_ok=True)
        
        with tarfile.open(model_tar, 'r:gz') as tar:
            tar.extractall(model_dir)
        
        # Find XGBoost model file (usually model.bst or similar)
        model_files = [f for f in os.listdir(model_dir) if f.endswith(('.bst', '.model', '.json'))]
        if not model_files:
            raise ValueError(f"No XGBoost model file found in {model_dir}")
        
        model_file = os.path.join(model_dir, model_files[0])
        print(f"  Loading model from {model_file}...")
        
        # Load XGBoost model
        booster = xgb.Booster()
        booster.load_model(model_file)
        
        # Extract feature importance
        print("  Extracting feature importance scores...")
        
        # Get importance scores (gain, cover, frequency)
        importance_gain = booster.get_score(importance_type='gain')
        importance_cover = booster.get_score(importance_type='cover')
        importance_frequency = booster.get_score(importance_type='weight')
        
        # Map feature indices to feature names
        # XGBoost uses f0, f1, f2, ... as feature names
        feature_map = {f'f{i}': name for i, name in enumerate(FEATURE_NAMES)}
        
        # Create feature importance dictionary
        feature_importance = {}
        
        for feat_idx, feat_name in feature_map.items():
            feature_importance[feat_name] = {
                'gain': importance_gain.get(feat_idx, 0.0),
                'cover': importance_cover.get(feat_idx, 0.0),
                'frequency': importance_frequency.get(feat_idx, 0.0),
            }
        
        # Sort by gain (most common importance metric)
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: x[1]['gain'],
            reverse=True
        )
        
        # Display top features
        print("\nTop 15 Most Important Features (by Gain):")
        print("-" * 70)
        print(f"{'Rank':<6} {'Feature Name':<35} {'Gain':<15} {'Cover':<15} {'Frequency':<15}")
        print("-" * 70)
        
        for rank, (feat_name, scores) in enumerate(sorted_features[:15], 1):
            print(f"{rank:<6} {feat_name:<35} {scores['gain']:<15.4f} {scores['cover']:<15.4f} {scores['frequency']:<15.4f}")
        
        # Calculate normalized importance (percentage)
        total_gain = sum(s['gain'] for s in feature_importance.values())
        if total_gain > 0:
            for feat_name in feature_importance:
                feature_importance[feat_name]['gain_pct'] = (
                    feature_importance[feat_name]['gain'] / total_gain * 100
                )
        
        # Return as dictionary with sorted list
        return {
            'by_gain': [
                {
                    'feature': name,
                    'gain': scores['gain'],
                    'gain_pct': scores.get('gain_pct', 0.0),
                    'cover': scores['cover'],
                    'frequency': scores['frequency']
                }
                for name, scores in sorted_features
            ],
            'raw': feature_importance
        }


def calculate_metrics(y_true: np.ndarray, y_pred_proba: np.ndarray, threshold: float = 0.5) -> Dict:
    """
    Calculate performance metrics
    
    Args:
        y_true: True labels
        y_pred_proba: Predicted probabilities
        threshold: Classification threshold
    
    Returns:
        Dictionary of metrics
    """
    # Convert probabilities to binary predictions
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # Calculate metrics
    metrics = {
        'roc_auc': roc_auc_score(y_true, y_pred_proba),
        'f1_score': f1_score(y_true, y_pred),
        'balanced_accuracy': balanced_accuracy_score(y_true, y_pred),
        'cohen_kappa': cohen_kappa_score(y_true, y_pred),
        'confusion_matrix': confusion_matrix(y_true, y_pred).tolist(),
    }
    
    # Add classification report
    report = classification_report(y_true, y_pred, output_dict=True)
    metrics['classification_report'] = report
    
    return metrics


def tune_threshold(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    thresholds: List[float] = None
) -> Dict:
    """
    Experiment with different classification thresholds to find optimal balance.
    Based on AWS blog approach: https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/
    
    Args:
        y_true: True labels
        y_pred_proba: Predicted probabilities
        thresholds: List of thresholds to test (default: 0.1 to 0.9 in 0.1 steps)
    
    Returns:
        Dictionary with threshold results and optimal threshold
    """
    if thresholds is None:
        thresholds = [round(0.1 + i * 0.1, 1) for i in range(9)]  # 0.1 to 0.9
    
    results = []
    
    print("=" * 70)
    print("Threshold Tuning Experiment")
    print("=" * 70)
    print(f"Testing {len(thresholds)} thresholds: {thresholds}")
    print()
    
    for threshold in thresholds:
        metrics = calculate_metrics(y_true, y_pred_proba, threshold)
        results.append({
            'threshold': threshold,
            'cohen_kappa': metrics['cohen_kappa'],
            'balanced_accuracy': metrics['balanced_accuracy'],
            'f1_score': metrics['f1_score'],
            'roc_auc': metrics['roc_auc'],
            'confusion_matrix': metrics['confusion_matrix']
        })
    
    # Find optimal threshold (maximize Cohen's Kappa while maintaining good balanced accuracy)
    # As per AWS blog: Cohen's Kappa keeps increasing with threshold without significant loss in balanced accuracy
    best_threshold_idx = max(range(len(results)), 
                            key=lambda i: results[i]['cohen_kappa'] + 0.5 * results[i]['balanced_accuracy'])
    best_result = results[best_threshold_idx]
    
    # Display results table
    print("Threshold Experiment Results:")
    print("-" * 100)
    print(f"{'Threshold':<12} {'Cohen Kappa':<15} {'Balanced Acc':<15} {'F1 Score':<15} {'ROC AUC':<15}")
    print("-" * 100)
    for r in results:
        marker = " ⭐" if r['threshold'] == best_result['threshold'] else ""
        print(f"{r['threshold']:<12.1f} {r['cohen_kappa']:<15.4f} {r['balanced_accuracy']:<15.4f} "
              f"{r['f1_score']:<15.4f} {r['roc_auc']:<15.4f}{marker}")
    print("-" * 100)
    print()
    
    print(f"⭐ Optimal Threshold: {best_result['threshold']:.1f}")
    print(f"   Cohen's Kappa: {best_result['cohen_kappa']:.4f}")
    print(f"   Balanced Accuracy: {best_result['balanced_accuracy']:.4f}")
    print(f"   F1 Score: {best_result['f1_score']:.4f}")
    print()
    
    return {
        'results': results,
        'optimal_threshold': best_result['threshold'],
        'optimal_metrics': {
            'cohen_kappa': best_result['cohen_kappa'],
            'balanced_accuracy': best_result['balanced_accuracy'],
            'f1_score': best_result['f1_score'],
            'roc_auc': best_result['roc_auc']
        }
    }


def evaluate_model(
    training_job_name: str,
    s3_bucket: str,
    s3_prefix: str,
    threshold: float = 0.5,
    cleanup_endpoint: bool = True,
    tune_thresholds: bool = False
) -> Dict:
    """
    Evaluate trained model
    
    Args:
        training_job_name: Name of the training job
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for test data
        threshold: Classification threshold
        cleanup_endpoint: If True, delete endpoint after evaluation
    
    Returns:
        Dictionary with evaluation results
    """
    print("=" * 70)
    print("Model Evaluation")
    print("=" * 70)
    print(f"Training job: {training_job_name}")
    print()
    
    # Load test data
    X_test, y_test = load_test_data_from_s3(s3_bucket, s3_prefix)
    print()
    
    # Get model predictor
    predictor, endpoint_name = get_model_from_training_job(training_job_name)
    print()
    
    # Make predictions
    y_pred_proba = predict_batch(predictor, X_test)
    print()
    
    # Threshold tuning if requested
    threshold_tuning_results = None
    if tune_thresholds:
        threshold_tuning_results = tune_threshold(y_test.values, y_pred_proba)
        # Use optimal threshold for final evaluation
        threshold = threshold_tuning_results['optimal_threshold']
        print(f"Using optimal threshold: {threshold:.2f}")
        print()
    
    # Calculate metrics
    print("Calculating metrics...")
    metrics = calculate_metrics(y_test.values, y_pred_proba, threshold)
    
    # Display results
    print("=" * 70)
    print("Evaluation Results")
    print("=" * 70)
    print(f"Classification Threshold: {threshold:.2f}")
    print(f"ROC AUC: {metrics['roc_auc']:.4f}")
    print(f"F1 Score: {metrics['f1_score']:.4f}")
    print(f"Balanced Accuracy: {metrics['balanced_accuracy']:.4f}")
    print(f"Cohen's Kappa: {metrics['cohen_kappa']:.4f}")
    print()
    
    print("Confusion Matrix:")
    cm = np.array(metrics['confusion_matrix'])
    print(f"  True Negatives:  {cm[0,0]:,}")
    print(f"  False Positives: {cm[0,1]:,}")
    print(f"  False Negatives: {cm[1,0]:,}")
    print(f"  True Positives:  {cm[1,1]:,}")
    print()
    
    print("Classification Report:")
    report = metrics['classification_report']
    for label in ['0', '1']:
        label_name = 'legitimate' if label == '0' else 'fraud'
        print(f"  {label_name} (label={label}):")
        print(f"    Precision: {report[label]['precision']:.4f}")
        print(f"    Recall:    {report[label]['recall']:.4f}")
        print(f"    F1-Score:  {report[label]['f1-score']:.4f}")
    print()
    
    # Check against benchmarks
    print("Benchmark Comparison:")
    benchmarks = {
        'roc_auc': 0.95,
        'f1_score': 0.75,
        'cohen_kappa': 0.75,
    }
    
    for metric_name, benchmark_value in benchmarks.items():
        actual_value = metrics[metric_name]
        status = "✅" if actual_value >= benchmark_value else "❌"
        print(f"  {metric_name}: {actual_value:.4f} (target: {benchmark_value:.4f}) {status}")
    print()
    
    # Cleanup endpoint if requested
    if cleanup_endpoint:
        print(f"Cleaning up endpoint: {endpoint_name}...")
        predictor.delete_endpoint()
        print("  ✅ Endpoint deleted")
    
    # Extract feature importance
    print("=" * 70)
    print("Feature Importance Analysis")
    print("=" * 70)
    feature_importance = extract_feature_importance(training_job_name, s3_bucket)
    print()
    
    # Save results
    results = {
        'training_job_name': training_job_name,
        'threshold': threshold,
        'metrics': metrics,
        'benchmarks': benchmarks,
        'meets_benchmarks': all(
            metrics[k] >= v for k, v in benchmarks.items()
        ),
        'feature_importance': feature_importance
    }
    
    # Add threshold tuning results if available
    if threshold_tuning_results:
        results['threshold_tuning'] = threshold_tuning_results
    
    # Save to S3
    try:
        results_key = f"fraud-detection/models/xgboost/evaluation/{training_job_name}/results.json"
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=results_key,
            Body=json.dumps(results, indent=2),
            ContentType='application/json'
        )
        print(f"✅ Results saved to: s3://{s3_bucket}/{results_key}")
    except Exception as e:
        print(f"⚠️  Could not save results to S3: {e}")
    
    return results


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Evaluate trained XGBoost model'
    )
    
    parser.add_argument('--training-job-name', type=str, required=True,
                       help='Name of the training job')
    parser.add_argument('--s3-bucket', type=str, default=None,
                       help='S3 bucket name (or use S3_BUCKET env var)')
    parser.add_argument('--s3-prefix', type=str,
                       default='fraud-detection/training/processed/',
                       help='S3 prefix for test data')
    parser.add_argument('--threshold', type=float, default=0.5,
                       help='Classification threshold (default: 0.5)')
    parser.add_argument('--tune-thresholds', action='store_true',
                       help='Experiment with thresholds 0.1-0.9 to find optimal (default: False)')
    parser.add_argument('--keep-endpoint', action='store_true',
                       help='Keep endpoint after evaluation (default: delete)')
    
    args = parser.parse_args()
    
    s3_bucket = args.s3_bucket or os.getenv('S3_BUCKET')
    if not s3_bucket:
        parser.error("S3 bucket is required")
    
    try:
        results = evaluate_model(
            training_job_name=args.training_job_name,
            s3_bucket=s3_bucket,
            s3_prefix=args.s3_prefix,
            threshold=args.threshold,
            cleanup_endpoint=not args.keep_endpoint,
            tune_thresholds=args.tune_thresholds
        )
        
        print("✅ Evaluation complete!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
