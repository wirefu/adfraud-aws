#!/usr/bin/env python3
"""
Deploy XGBoost Model to SageMaker Endpoint

Deploys a trained SageMaker XGBoost model to a production endpoint with auto-scaling.
Supports deployment from training job or model artifact S3 path.

Usage:
    # Deploy from training job
    python scripts/deploy_model_sagemaker.py \
        --training-job-name fraudguard-xgboost-baseline-2024-11-13-123456 \
        --endpoint-name fraudguard-xgboost-endpoint \
        --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole

    # Deploy from model artifact
    python scripts/deploy_model_sagemaker.py \
        --model-artifact s3://bucket/fraud-detection/models/xgboost/baseline/model.tar.gz \
        --endpoint-name fraudguard-xgboost-endpoint \
        --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole
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
from sagemaker.xgboost.model import XGBoostModel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_stack_outputs(stack_name: str) -> Dict[str, str]:
    """
    Get CloudFormation stack outputs
    
    Args:
        stack_name: CloudFormation stack name
    
    Returns:
        Dictionary of output key-value pairs
    """
    cf_client = boto3.client('cloudformation')
    try:
        stack = cf_client.describe_stacks(StackName=stack_name)
        outputs = {o['OutputKey']: o['OutputValue'] 
                  for o in stack['Stacks'][0].get('Outputs', [])}
        return outputs
    except Exception as e:
        print(f"  ⚠️  Could not get stack outputs: {e}")
        return {}


def get_model_from_training_job(training_job_name: str) -> Dict[str, str]:
    """
    Get model artifact and role from training job
    
    Args:
        training_job_name: Name of the training job
    
    Returns:
        Dictionary with model_artifact and role_arn
    """
    sess = sagemaker.Session()
    
    print(f"Getting model from training job: {training_job_name}...")
    
    try:
        training_job = sess.sagemaker_client.describe_training_job(
            TrainingJobName=training_job_name
        )
        
        model_artifact = training_job['ModelArtifacts']['S3ModelArtifacts']
        role_arn = training_job['RoleArn']
        
        print(f"  ✅ Model artifact: {model_artifact}")
        print(f"  ✅ Role ARN: {role_arn}")
        
        return {
            'model_artifact': model_artifact,
            'role_arn': role_arn
        }
    except Exception as e:
        print(f"  ❌ Error getting training job: {e}")
        raise


def setup_auto_scaling(
    endpoint_name: str,
    min_capacity: int = 1,
    max_capacity: int = 4,
    target_value: float = 70.0,
    scale_in_cooldown: int = 300,
    scale_out_cooldown: int = 60
) -> None:
    """
    Set up auto-scaling for SageMaker endpoint using Application Auto Scaling
    
    Args:
        endpoint_name: Name of the SageMaker endpoint
        min_capacity: Minimum number of instances
        max_capacity: Maximum number of instances
        target_value: Target CPU utilization percentage
        scale_in_cooldown: Cooldown period for scale-in (seconds)
        scale_out_cooldown: Cooldown period for scale-out (seconds)
    """
    print(f"\nSetting up auto-scaling for endpoint: {endpoint_name}...")
    
    autoscaling_client = boto3.client('application-autoscaling')
    sagemaker_client = boto3.client('sagemaker')
    
    # Get endpoint details to find resource ID
    endpoint_details = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
    endpoint_config = sagemaker_client.describe_endpoint_config(
        EndpointConfigName=endpoint_details['EndpointConfigName']
    )
    
    # Resource ID format: endpoint/<endpoint-name>/variant/<variant-name>
    resource_id = f"endpoint/{endpoint_name}/variant/AllTraffic"
    
    # Register scalable target
    print(f"  Registering scalable target: {resource_id}")
    try:
        autoscaling_client.register_scalable_target(
            ServiceNamespace='sagemaker',
            ResourceId=resource_id,
            ScalableDimension='sagemaker:variant:DesiredInstanceCount',
            MinCapacity=min_capacity,
            MaxCapacity=max_capacity
        )
        print(f"  ✅ Scalable target registered")
    except autoscaling_client.exceptions.ValidationException as e:
        if 'already exists' in str(e).lower():
            print(f"  ℹ️  Scalable target already exists, updating...")
            autoscaling_client.register_scalable_target(
                ServiceNamespace='sagemaker',
                ResourceId=resource_id,
                ScalableDimension='sagemaker:variant:DesiredInstanceCount',
                MinCapacity=min_capacity,
                MaxCapacity=max_capacity
            )
        else:
            raise
    
    # Create target tracking scaling policy
    print(f"  Creating target tracking scaling policy...")
    policy_name = f"{endpoint_name}-target-tracking-policy"
    
    try:
        autoscaling_client.put_scaling_policy(
            ServiceNamespace='sagemaker',
            ResourceId=resource_id,
            ScalableDimension='sagemaker:variant:DesiredInstanceCount',
            PolicyName=policy_name,
            PolicyType='TargetTrackingScaling',
            TargetTrackingScalingPolicyConfiguration={
                'TargetValue': target_value,
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance'
                },
                'ScaleInCooldown': scale_in_cooldown,
                'ScaleOutCooldown': scale_out_cooldown
            }
        )
        print(f"  ✅ Auto-scaling policy created: {policy_name}")
    except Exception as e:
        print(f"  ⚠️  Could not create scaling policy: {e}")
        print(f"  You may need to set up auto-scaling manually in the AWS Console")
        raise
    
    print(f"  ✅ Auto-scaling configured:")
    print(f"     Min capacity: {min_capacity}")
    print(f"     Max capacity: {max_capacity}")
    print(f"     Target: {target_value}% CPU utilization")


def deploy_model(
    model_artifact: str,
    role_arn: str,
    endpoint_name: str,
    instance_type: str = 'ml.t2.medium',
    initial_instance_count: int = 1,
    framework_version: str = '1.7-1',
    enable_auto_scaling: bool = True,
    wait: bool = True
) -> str:
    """
    Deploy XGBoost model to SageMaker endpoint
    
    Args:
        model_artifact: S3 path to model artifact (model.tar.gz)
        role_arn: SageMaker execution role ARN
        endpoint_name: Name for the endpoint
        instance_type: Instance type for the endpoint
        initial_instance_count: Initial number of instances
        framework_version: XGBoost framework version
        enable_auto_scaling: If True, set up auto-scaling after deployment
        wait: If True, wait for endpoint to be ready
    
    Returns:
        Endpoint name
    """
    print("=" * 70)
    print("Deploying Model to SageMaker Endpoint")
    print("=" * 70)
    print(f"Model artifact: {model_artifact}")
    print(f"Endpoint name: {endpoint_name}")
    print(f"Instance type: {instance_type}")
    print(f"Initial instances: {initial_instance_count}")
    print()
    
    sess = sagemaker.Session()
    
    # Create XGBoost model
    print("Creating SageMaker model...")
    model = XGBoostModel(
        model_data=model_artifact,
        role=role_arn,
        framework_version=framework_version,
        sagemaker_session=sess
    )
    
    # Check if endpoint already exists
    sagemaker_client = boto3.client('sagemaker')
    try:
        existing_endpoint = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        endpoint_status = existing_endpoint['EndpointStatus']
        
        if endpoint_status in ['InService', 'Creating', 'Updating']:
            print(f"  ⚠️  Endpoint '{endpoint_name}' already exists (status: {endpoint_status})")
            response = input("  Do you want to update it? (yes/no): ").strip().lower()
            
            if response == 'yes':
                print(f"  Updating endpoint...")
                # Update endpoint with new model
                model.deploy(
                    initial_instance_count=initial_instance_count,
                    instance_type=instance_type,
                    endpoint_name=endpoint_name,
                    serializer=sagemaker.serializers.CSVSerializer(),
                    deserializer=sagemaker.deserializers.CSVDeserializer(),
                    update_endpoint=True,
                    wait=wait
                )
                print(f"  ✅ Endpoint updated")
            else:
                print(f"  ℹ️  Keeping existing endpoint")
                return endpoint_name
        else:
            # Endpoint exists but not in service - delete and recreate
            print(f"  Endpoint exists but status is '{endpoint_status}', deleting...")
            sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
            print(f"  Waiting for deletion to complete...")
            waiter = sagemaker_client.get_waiter('endpoint_deleted')
            waiter.wait(EndpointName=endpoint_name)
            print(f"  ✅ Endpoint deleted")
    except sagemaker_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            # Endpoint doesn't exist, proceed with creation
            print(f"  Creating new endpoint...")
        else:
            raise
    
    # Deploy model
    print(f"Deploying model to endpoint: {endpoint_name}...")
    predictor = model.deploy(
        initial_instance_count=initial_instance_count,
        instance_type=instance_type,
        endpoint_name=endpoint_name,
        serializer=sagemaker.serializers.CSVSerializer(),
        deserializer=sagemaker.deserializers.CSVDeserializer(),
        wait=wait
    )
    
    if wait:
        print(f"  ✅ Endpoint deployed and ready!")
    else:
        print(f"  ✅ Endpoint deployment started (running in background)")
    
    # Set up auto-scaling if requested
    if enable_auto_scaling and wait:
        try:
            setup_auto_scaling(endpoint_name)
        except Exception as e:
            print(f"  ⚠️  Auto-scaling setup failed: {e}")
            print(f"  You can set it up manually later")
    
    return endpoint_name


def update_lambda_environment(
    stack_name: str,
    endpoint_name: str,
    function_name: Optional[str] = None
) -> None:
    """
    Update Lambda function environment variable with endpoint name
    
    Args:
        stack_name: CloudFormation stack name
        endpoint_name: SageMaker endpoint name
        function_name: Lambda function name (defaults to stack-name-orchestrator)
    """
    if not function_name:
        function_name = f"{stack_name}-orchestrator"
    
    print(f"\nUpdating Lambda environment variable...")
    print(f"  Function: {function_name}")
    print(f"  Endpoint: {endpoint_name}")
    
    lambda_client = boto3.client('lambda')
    
    try:
        # Get current configuration
        current_config = lambda_client.get_function_configuration(
            FunctionName=function_name
        )
        
        # Update environment variables
        env_vars = current_config.get('Environment', {}).get('Variables', {})
        env_vars['SAGEMAKER_ENDPOINT'] = endpoint_name
        
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={'Variables': env_vars}
        )
        
        print(f"  ✅ Lambda environment variable updated")
        print(f"     SAGEMAKER_ENDPOINT = {endpoint_name}")
    except Exception as e:
        print(f"  ⚠️  Could not update Lambda: {e}")
        print(f"  You may need to update it manually in the AWS Console or CloudFormation template")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Deploy XGBoost model to SageMaker endpoint',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy from training job
  python scripts/deploy_model_sagemaker.py \\
      --training-job-name fraudguard-xgboost-baseline-2024-11-13-123456 \\
      --endpoint-name fraudguard-xgboost-endpoint \\
      --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole

  # Deploy from model artifact
  python scripts/deploy_model_sagemaker.py \\
      --model-artifact s3://bucket/fraud-detection/models/xgboost/baseline/model.tar.gz \\
      --endpoint-name fraudguard-xgboost-endpoint \\
      --sagemaker-role-arn arn:aws:iam::123456789012:role/SageMakerRole

  # Deploy with auto-detection from stack
  python scripts/deploy_model_sagemaker.py \\
      --training-job-name fraudguard-xgboost-baseline-2024-11-13-123456 \\
      --endpoint-name fraudguard-xgboost-endpoint \\
      --stack-name fraudguard-ai-dev \\
      --update-lambda
        """
    )
    
    # Model source (mutually exclusive)
    model_group = parser.add_mutually_exclusive_group(required=True)
    model_group.add_argument(
        '--training-job-name',
        type=str,
        help='Name of the training job to deploy'
    )
    model_group.add_argument(
        '--model-artifact',
        type=str,
        help='S3 path to model artifact (model.tar.gz)'
    )
    
    # Endpoint configuration
    parser.add_argument(
        '--endpoint-name',
        type=str,
        required=True,
        help='Name for the SageMaker endpoint'
    )
    
    parser.add_argument(
        '--instance-type',
        type=str,
        default='ml.t2.medium',
        help='Instance type for the endpoint (default: ml.t2.medium)'
    )
    
    parser.add_argument(
        '--initial-instance-count',
        type=int,
        default=1,
        help='Initial number of instances (default: 1)'
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
        help='CloudFormation stack name (auto-detects role if not provided)'
    )
    
    parser.add_argument(
        '--framework-version',
        type=str,
        default='1.7-1',
        help='XGBoost framework version (default: 1.7-1)'
    )
    
    # Auto-scaling configuration
    parser.add_argument(
        '--no-auto-scaling',
        action='store_true',
        help='Disable auto-scaling setup'
    )
    
    parser.add_argument(
        '--min-capacity',
        type=int,
        default=1,
        help='Minimum number of instances for auto-scaling (default: 1)'
    )
    
    parser.add_argument(
        '--max-capacity',
        type=int,
        default=4,
        help='Maximum number of instances for auto-scaling (default: 4)'
    )
    
    # Lambda update
    parser.add_argument(
        '--update-lambda',
        action='store_true',
        help='Update Lambda function environment variable with endpoint name'
    )
    
    parser.add_argument(
        '--lambda-function-name',
        type=str,
        help='Lambda function name (defaults to stack-name-orchestrator)'
    )
    
    # Execution options
    parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Don\'t wait for endpoint to be ready (deploy asynchronously)'
    )
    
    args = parser.parse_args()
    
    # Resolve SageMaker role
    sagemaker_role_arn = args.sagemaker_role_arn or os.getenv('SAGEMAKER_ROLE_ARN')
    
    if not sagemaker_role_arn and args.stack_name:
        # Try to get from CloudFormation
        outputs = get_stack_outputs(args.stack_name)
        sagemaker_role_arn = outputs.get('SageMakerExecutionRoleArn')
        
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
                    print(f"  ✅ Auto-detected SageMaker role from Terraform: {sagemaker_role_arn}")
            except:
                pass
    
    if not sagemaker_role_arn:
        parser.error("SageMaker role ARN must be provided via --sagemaker-role-arn, SAGEMAKER_ROLE_ARN env var, or --stack-name")
    
    # Get model artifact and role
    if args.training_job_name:
        model_info = get_model_from_training_job(args.training_job_name)
        model_artifact = model_info['model_artifact']
        # Use role from training job if not provided
        if not args.sagemaker_role_arn:
            sagemaker_role_arn = model_info['role_arn']
    else:
        model_artifact = args.model_artifact
    
    # Deploy model
    try:
        endpoint_name = deploy_model(
            model_artifact=model_artifact,
            role_arn=sagemaker_role_arn,
            endpoint_name=args.endpoint_name,
            instance_type=args.instance_type,
            initial_instance_count=args.initial_instance_count,
            framework_version=args.framework_version,
            enable_auto_scaling=not args.no_auto_scaling,
            wait=not args.no_wait
        )
        
        # Update Lambda if requested
        if args.update_lambda and args.stack_name:
            update_lambda_environment(
                stack_name=args.stack_name,
                endpoint_name=endpoint_name,
                function_name=args.lambda_function_name
            )
        
        print("\n" + "=" * 70)
        print("✅ Deployment Complete!")
        print("=" * 70)
        print(f"Endpoint name: {endpoint_name}")
        sess = sagemaker.Session()
        account_id = boto3.client('sts').get_caller_identity()['Account']
        region = sess.boto_region_name
        print(f"Endpoint ARN: arn:aws:sagemaker:{region}:{account_id}:endpoint/{endpoint_name}")
        print(f"\nTest the endpoint:")
        print(f"  aws sagemaker-runtime invoke-endpoint \\")
        print(f"    --endpoint-name {endpoint_name} \\")
        print(f"    --content-type text/csv \\")
        print(f"    --body file://test_data.csv \\")
        print(f"    response.json")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
