#!/usr/bin/env python3
"""
Test SageMaker Endpoint Deployment

Tests a deployed SageMaker endpoint with sample requests, measures latency and throughput,
and verifies inference results.

Usage:
    python scripts/test_sagemaker_endpoint.py \
        --endpoint-name fraudguard-xgboost-endpoint \
        --num-requests 100 \
        --batch-size 10
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import boto3
import numpy as np
import pandas as pd
import sagemaker
from sagemaker.predictor import Predictor
from sagemaker.serializers import CSVSerializer
from sagemaker.deserializers import CSVDeserializer

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.feature_engineering import FEATURE_NAMES


def generate_sample_features(num_samples: int = 1) -> List[List[float]]:
    """
    Generate sample feature vectors for testing
    
    Args:
        num_samples: Number of samples to generate
    
    Returns:
        List of feature vectors (each is a list of 29 floats)
    """
    # Generate random but realistic feature values
    np.random.seed(42)
    
    samples = []
    for _ in range(num_samples):
        # Generate features with realistic ranges
        features = []
        
        # IP click count (0-1000)
        features.append(float(np.random.randint(0, 1000)))
        
        # Device click count (0-100)
        features.append(float(np.random.randint(0, 100)))
        
        # Time since last click (0-86400 seconds)
        features.append(float(np.random.randint(0, 86400)))
        
        # Hour of day (0-23)
        features.append(float(np.random.randint(0, 24)))
        
        # Day of week (0-6)
        features.append(float(np.random.randint(0, 7)))
        
        # IP reputation features (0 or 1)
        features.extend([float(np.random.choice([0, 1])) for _ in range(5)])
        
        # User agent features (0-1)
        features.extend([float(np.random.random()) for _ in range(3)])
        
        # Device features (0-1)
        features.extend([float(np.random.random()) for _ in range(4)])
        
        # Conversion features (0-1)
        features.extend([float(np.random.random()) for _ in range(2)])
        
        # Engagement features (0-1)
        features.extend([float(np.random.random()) for _ in range(2)])
        
        # Click injection features (0-1)
        features.extend([float(np.random.random()) for _ in range(2)])
        
        # Categorical features (country: 0-9, OS: 0-4)
        features.append(float(np.random.randint(0, 10)))  # country
        features.append(float(np.random.randint(0, 5)))  # os
        
        # Ensure we have exactly 29 features
        assert len(features) == 29, f"Expected 29 features, got {len(features)}"
        
        samples.append(features)
    
    return samples


def test_endpoint_single(
    predictor: Predictor,
    feature_vector: List[float],
    verbose: bool = False
) -> Tuple[float, float]:
    """
    Test single request to endpoint
    
    Args:
        predictor: SageMaker predictor
        feature_vector: Feature vector to send
        verbose: If True, print details
    
    Returns:
        Tuple of (prediction, latency_ms)
    """
    # Convert to CSV format
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(feature_vector)
    csv_data = csv_buffer.getvalue()
    
    # Measure latency
    start_time = time.time()
    try:
        response = predictor.predict(csv_data)
        latency_ms = (time.time() - start_time) * 1000
        
        # Parse response
        if isinstance(response, list):
            prediction = float(response[0])
        else:
            prediction = float(response)
        
        if verbose:
            print(f"  Prediction: {prediction:.4f}, Latency: {latency_ms:.2f}ms")
        
        return prediction, latency_ms
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        print(f"  ❌ Error: {e}")
        return None, latency_ms


def test_endpoint_batch(
    predictor: Predictor,
    feature_vectors: List[List[float]],
    batch_size: int = 10
) -> Dict:
    """
    Test endpoint with batch of requests
    
    Args:
        predictor: SageMaker predictor
        feature_vectors: List of feature vectors
        batch_size: Number of requests per batch
    
    Returns:
        Dictionary with test results
    """
    print(f"Testing endpoint with {len(feature_vectors)} requests (batch size: {batch_size})...")
    
    all_predictions = []
    all_latencies = []
    errors = []
    
    total_batches = (len(feature_vectors) + batch_size - 1) // batch_size
    
    for i in range(0, len(feature_vectors), batch_size):
        batch = feature_vectors[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        batch_start = time.time()
        
        for feature_vector in batch:
            prediction, latency = test_endpoint_single(predictor, feature_vector)
            
            if prediction is not None:
                all_predictions.append(prediction)
                all_latencies.append(latency)
            else:
                errors.append(len(all_predictions))
        
        batch_time = (time.time() - batch_start) * 1000
        
        if batch_num % 10 == 0 or batch_num == total_batches:
            print(f"  Processed {batch_num}/{total_batches} batches "
                  f"({min(i+batch_size, len(feature_vectors))}/{len(feature_vectors)} samples)")
    
    # Calculate statistics
    if all_predictions:
        results = {
            'total_requests': len(feature_vectors),
            'successful_requests': len(all_predictions),
            'failed_requests': len(errors),
            'success_rate': len(all_predictions) / len(feature_vectors) * 100,
            'predictions': {
                'mean': float(np.mean(all_predictions)),
                'std': float(np.std(all_predictions)),
                'min': float(np.min(all_predictions)),
                'max': float(np.max(all_predictions)),
                'median': float(np.median(all_predictions))
            },
            'latency_ms': {
                'mean': float(np.mean(all_latencies)),
                'std': float(np.std(all_latencies)),
                'min': float(np.min(all_latencies)),
                'max': float(np.max(all_latencies)),
                'median': float(np.median(all_latencies)),
                'p50': float(np.percentile(all_latencies, 50)),
                'p95': float(np.percentile(all_latencies, 95)),
                'p99': float(np.percentile(all_latencies, 99))
            },
            'throughput': {
                'requests_per_second': len(all_predictions) / (sum(all_latencies) / 1000) if all_latencies else 0
            },
            'errors': errors
        }
    else:
        results = {
            'total_requests': len(feature_vectors),
            'successful_requests': 0,
            'failed_requests': len(feature_vectors),
            'success_rate': 0.0,
            'error': 'All requests failed'
        }
    
    return results


def check_endpoint_health(endpoint_name: str) -> Dict:
    """
    Check endpoint health and status
    
    Args:
        endpoint_name: Name of the endpoint
    
    Returns:
        Dictionary with endpoint status information
    """
    print(f"Checking endpoint health: {endpoint_name}...")
    
    sagemaker_client = boto3.client('sagemaker')
    
    try:
        endpoint_info = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        endpoint_config_info = sagemaker_client.describe_endpoint_config(
            EndpointConfigName=endpoint_info['EndpointConfigName']
        )
        
        status = endpoint_info['EndpointStatus']
        creation_time = endpoint_info['CreationTime']
        last_modified = endpoint_info.get('LastModifiedTime', creation_time)
        
        # Get variant information
        variants = endpoint_config_info['ProductionVariants']
        variant_info = variants[0] if variants else {}
        
        health_info = {
            'endpoint_name': endpoint_name,
            'status': status,
            'creation_time': creation_time.isoformat(),
            'last_modified': last_modified.isoformat(),
            'instance_type': variant_info.get('InstanceType', 'unknown'),
            'initial_instance_count': variant_info.get('InitialInstanceCount', 0),
            'variant_name': variant_info.get('VariantName', 'unknown'),
            'is_healthy': status == 'InService'
        }
        
        print(f"  Status: {status}")
        print(f"  Instance Type: {health_info['instance_type']}")
        print(f"  Instance Count: {health_info['initial_instance_count']}")
        
        return health_info
    except Exception as e:
        print(f"  ❌ Error checking endpoint: {e}")
        return {'error': str(e), 'is_healthy': False}


def test_endpoint(
    endpoint_name: str,
    num_requests: int = 100,
    batch_size: int = 10,
    use_sample_data: bool = True,
    sample_data_file: str = None
) -> Dict:
    """
    Test SageMaker endpoint with sample requests
    
    Args:
        endpoint_name: Name of the SageMaker endpoint
        num_requests: Number of test requests to send
        batch_size: Batch size for requests
        use_sample_data: If True, generate sample features
        sample_data_file: Path to CSV file with test data (optional)
    
    Returns:
        Dictionary with test results
    """
    print("=" * 70)
    print("SageMaker Endpoint Testing")
    print("=" * 70)
    print(f"Endpoint: {endpoint_name}")
    print()
    
    # Check endpoint health
    health_info = check_endpoint_health(endpoint_name)
    print()
    
    if not health_info.get('is_healthy'):
        return {
            'health_check': health_info,
            'error': 'Endpoint is not healthy'
        }
    
    # Create predictor
    print("Creating predictor...")
    predictor = Predictor(
        endpoint_name=endpoint_name,
        serializer=CSVSerializer(),
        deserializer=CSVDeserializer()
    )
    print("  ✅ Predictor created")
    print()
    
    # Load or generate test data
    if sample_data_file:
        print(f"Loading test data from: {sample_data_file}")
        df = pd.read_csv(sample_data_file)
        # Assume last column is label, rest are features
        feature_vectors = df.iloc[:, :-1].values.tolist()
        if len(feature_vectors) > num_requests:
            feature_vectors = feature_vectors[:num_requests]
        print(f"  ✅ Loaded {len(feature_vectors)} samples")
    else:
        print(f"Generating {num_requests} sample feature vectors...")
        feature_vectors = generate_sample_features(num_requests)
        print(f"  ✅ Generated {len(feature_vectors)} samples")
    
    print()
    
    # Run tests
    test_results = test_endpoint_batch(predictor, feature_vectors, batch_size)
    print()
    
    # Display results
    print("=" * 70)
    print("Test Results")
    print("=" * 70)
    
    if 'error' in test_results:
        print(f"❌ {test_results['error']}")
        return {'health_check': health_info, 'test_results': test_results}
    
    print(f"Total Requests: {test_results['total_requests']}")
    print(f"Successful: {test_results['successful_requests']}")
    print(f"Failed: {test_results['failed_requests']}")
    print(f"Success Rate: {test_results['success_rate']:.2f}%")
    print()
    
    print("Prediction Statistics:")
    pred_stats = test_results['predictions']
    print(f"  Mean: {pred_stats['mean']:.4f}")
    print(f"  Std:  {pred_stats['std']:.4f}")
    print(f"  Min:  {pred_stats['min']:.4f}")
    print(f"  Max:  {pred_stats['max']:.4f}")
    print(f"  Median: {pred_stats['median']:.4f}")
    print()
    
    print("Latency Statistics (ms):")
    latency_stats = test_results['latency_ms']
    print(f"  Mean: {latency_stats['mean']:.2f}ms")
    print(f"  Std:  {latency_stats['std']:.2f}ms")
    print(f"  Min:  {latency_stats['min']:.2f}ms")
    print(f"  Max:  {latency_stats['max']:.2f}ms")
    print(f"  Median (p50): {latency_stats['p50']:.2f}ms")
    print(f"  p95: {latency_stats['p95']:.2f}ms")
    print(f"  p99: {latency_stats['p99']:.2f}ms")
    print()
    
    print("Throughput:")
    throughput = test_results['throughput']
    print(f"  Requests per second: {throughput['requests_per_second']:.2f}")
    print()
    
    # Operational metrics check
    print("Operational Metrics:")
    print(f"  ✅ Success rate: {test_results['success_rate']:.2f}% "
          f"{'✅' if test_results['success_rate'] >= 99.0 else '⚠️'}")
    print(f"  ✅ Mean latency: {latency_stats['mean']:.2f}ms "
          f"{'✅' if latency_stats['mean'] < 500 else '⚠️'}")
    print(f"  ✅ p95 latency: {latency_stats['p95']:.2f}ms "
          f"{'✅' if latency_stats['p95'] < 1000 else '⚠️'}")
    print()
    
    return {
        'health_check': health_info,
        'test_results': test_results
    }


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Test SageMaker endpoint deployment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with generated sample data
  python scripts/test_sagemaker_endpoint.py \\
      --endpoint-name fraudguard-xgboost-endpoint \\
      --num-requests 100

  # Test with custom test data file
  python scripts/test_sagemaker_endpoint.py \\
      --endpoint-name fraudguard-xgboost-endpoint \\
      --sample-data-file data/test_features.csv \\
      --num-requests 50
        """
    )
    
    parser.add_argument(
        '--endpoint-name',
        type=str,
        required=True,
        help='Name of the SageMaker endpoint'
    )
    
    parser.add_argument(
        '--num-requests',
        type=int,
        default=100,
        help='Number of test requests to send (default: 100)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Batch size for requests (default: 10)'
    )
    
    parser.add_argument(
        '--sample-data-file',
        type=str,
        help='Path to CSV file with test data (optional, generates samples if not provided)'
    )
    
    parser.add_argument(
        '--output-file',
        type=str,
        help='Path to save test results JSON file (optional)'
    )
    
    args = parser.parse_args()
    
    try:
        results = test_endpoint(
            endpoint_name=args.endpoint_name,
            num_requests=args.num_requests,
            batch_size=args.batch_size,
            sample_data_file=args.sample_data_file
        )
        
        # Save results if requested
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Results saved to: {args.output_file}")
        
        # Exit with error code if tests failed
        if 'error' in results or results.get('test_results', {}).get('success_rate', 0) < 99.0:
            sys.exit(1)
        
        print("✅ All tests passed!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
