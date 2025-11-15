#!/usr/bin/env python3
"""
Fix SageMaker Endpoint Deployment

Redeploys the endpoint with proper CSV serializer/deserializer configuration
to fix the issue where endpoint returns [] instead of predictions.
"""

import argparse
import boto3
import sagemaker
from sagemaker.xgboost.model import XGBoostModel
from sagemaker.serializers import CSVSerializer
from sagemaker.deserializers import CSVDeserializer


def get_model_artifact_from_endpoint(endpoint_name: str) -> str:
    """Get model artifact S3 path from existing endpoint"""
    sagemaker_client = boto3.client('sagemaker')
    
    # Get endpoint config
    endpoint = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
    endpoint_config_name = endpoint['EndpointConfigName']
    
    # Get endpoint config
    endpoint_config = sagemaker_client.describe_endpoint_config(
        EndpointConfigName=endpoint_config_name
    )
    
    # Get model name
    model_name = endpoint_config['ProductionVariants'][0]['ModelName']
    
    # Get model details
    model = sagemaker_client.describe_model(ModelName=model_name)
    model_data_url = model['PrimaryContainer']['ModelDataUrl']
    
    return model_data_url


def redeploy_endpoint(
    endpoint_name: str,
    sagemaker_role_arn: str,
    model_s3_path: str = None,
    instance_type: str = 'ml.m5.large',
    framework_version: str = '1.7-1'
):
    """
    Redeploy endpoint with proper CSV serializer/deserializer
    
    Args:
        endpoint_name: Name of the endpoint to redeploy
        sagemaker_role_arn: IAM role ARN for SageMaker
        model_s3_path: S3 path to model artifact (if None, will get from existing endpoint)
        instance_type: Instance type for endpoint
        framework_version: XGBoost framework version
    """
    sess = sagemaker.Session()
    
    # Get model artifact BEFORE deleting endpoint (if not provided)
    if model_s3_path is None:
        print(f"Getting model artifact from existing endpoint: {endpoint_name}")
        try:
            model_s3_path = get_model_artifact_from_endpoint(endpoint_name)
            print(f"  Model artifact: {model_s3_path}")
        except Exception as e:
            print(f"  ⚠️  Could not get model from endpoint: {e}")
            print("  Please provide --model-s3-path directly")
            raise
    
    print()
    print("=" * 80)
    print("🔧 REDEPLOYING ENDPOINT WITH PROPER CONFIGURATION")
    print("=" * 80)
    print()
    print(f"📦 Model: {model_s3_path}")
    print(f"🎯 Endpoint: {endpoint_name}")
    print(f"💻 Instance: {instance_type}")
    print(f"🔧 Framework: XGBoost {framework_version}")
    print()
    
    # Delete existing endpoint first
    print("⚠️  Deleting existing endpoint...")
    try:
        sess.sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
        print("  ✅ Endpoint deletion initiated")
        
        # Wait for deletion
        print("  ⏳ Waiting for endpoint to be deleted (this may take a few minutes)...")
        waiter = sess.sagemaker_client.get_waiter('endpoint_deleted')
        waiter.wait(EndpointName=endpoint_name)
        print("  ✅ Endpoint deleted")
    except Exception as e:
        if 'NotFound' in str(e) or 'does not exist' in str(e):
            print("  ℹ️  Endpoint doesn't exist, proceeding with deployment")
        else:
            print(f"  ⚠️  Error deleting endpoint: {e}")
            print("  Continuing anyway...")
    
    print()
    
    # Create model with proper configuration
    print("📦 Creating XGBoost model...")
    model = XGBoostModel(
        model_data=model_s3_path,
        role=sagemaker_role_arn,
        framework_version=framework_version,
        py_version='py3',
    )
    print("  ✅ Model created")
    print()
    
    # Deploy endpoint with CSV serializer/deserializer
    print("⏳ Deploying endpoint with CSV serializer/deserializer...")
    print("  (This may take 5-10 minutes)")
    print()
    
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name,
        serializer=CSVSerializer(),      # ✅ Required for CSV input
        deserializer=CSVDeserializer()    # ✅ Required for CSV output
    )
    
    print()
    print("=" * 80)
    print("✅ ENDPOINT REDEPLOYED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print(f"🔗 Endpoint Name: {endpoint_name}")
    print(f"📊 Endpoint ARN: {predictor.endpoint_name}")
    print()
    print("💡 Next Steps:")
    print("   1. Test endpoint with sample requests")
    print("   2. Verify predictions are returned (not [])")
    print("   3. Run model evaluation")
    
    return predictor


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Redeploy SageMaker endpoint with proper CSV configuration')
    parser.add_argument('--endpoint-name', type=str, 
                       default='fraudguard-xgboost-endpoint',
                       help='Endpoint name to redeploy')
    parser.add_argument('--sagemaker-role-arn', type=str, required=True,
                       help='SageMaker execution role ARN')
    parser.add_argument('--model-s3-path', type=str, default=None,
                       help='S3 path to model artifact (optional, will auto-detect from endpoint)')
    parser.add_argument('--instance-type', type=str, default='ml.m5.large',
                       help='Instance type for endpoint')
    parser.add_argument('--framework-version', type=str, default='1.7-1',
                       help='XGBoost framework version')
    
    args = parser.parse_args()
    
    redeploy_endpoint(
        endpoint_name=args.endpoint_name,
        sagemaker_role_arn=args.sagemaker_role_arn,
        model_s3_path=args.model_s3_path,
        instance_type=args.instance_type,
        framework_version=args.framework_version
    )

