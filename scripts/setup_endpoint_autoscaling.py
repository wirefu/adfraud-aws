#!/usr/bin/env python3
"""
Set up auto-scaling for SageMaker endpoint.

This script:
1. Creates IAM role for Application Auto Scaling (if needed)
2. Registers the endpoint as a scalable target
3. Creates a target tracking scaling policy
"""

import boto3
import json
import sys
from typing import Optional

# Configuration
ENDPOINT_NAME = "fraudguard-xgboost-endpoint"
VARIANT_NAME = "AllTraffic"
MIN_CAPACITY = 1
MAX_CAPACITY = 3
TARGET_VALUE = 70.0  # Target 70% of max invocations per instance
SAGEMAKER_ROLE_ARN = "arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role"
REGION = "us-east-1"

# AWS Clients
iam = boto3.client("iam", region_name=REGION)
autoscaling = boto3.client("application-autoscaling", region_name=REGION)
sagemaker = boto3.client("sagemaker", region_name=REGION)


def create_autoscaling_role() -> str:
    """Create IAM role for Application Auto Scaling if it doesn't exist."""
    role_name = "fraudguard-ai-autoscaling-role"
    
    try:
        # Check if role exists
        role = iam.get_role(RoleName=role_name)
        print(f"✅ Auto-scaling role already exists: {role_name}")
        return role["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        print(f"📝 Creating auto-scaling role: {role_name}")
    
    # Create trust policy for Application Auto Scaling
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "application-autoscaling.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # Create role
    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="IAM role for SageMaker endpoint auto-scaling",
        Tags=[
            {"Key": "Project", "Value": "FraudGuardAI"},
            {"Key": "Environment", "Value": "dev"},
            {"Key": "ManagedBy", "Value": "Terraform"}
        ]
    )
    
    role_arn = role["Role"]["Arn"]
    print(f"  ✅ Role created: {role_arn}")
    
    # Attach policy for SageMaker endpoint management
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "sagemaker:DescribeEndpoint",
                    "sagemaker:DescribeEndpointConfig",
                    "sagemaker:UpdateEndpointWeightsAndCapacities",
                    "sagemaker:DescribeModel",
                    "cloudwatch:PutMetricAlarm",
                    "cloudwatch:DescribeAlarms",
                    "cloudwatch:DeleteAlarms",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:SetAlarmState"
                ],
                "Resource": "*"
            }
        ]
    }
    
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="SageMakerEndpointAutoScalingPolicy",
        PolicyDocument=json.dumps(policy_document)
    )
    print(f"  ✅ Policy attached to role")
    
    return role_arn


def register_scalable_target(role_arn: str) -> bool:
    """Register the endpoint variant as a scalable target."""
    resource_id = f"endpoint/{ENDPOINT_NAME}/variant/{VARIANT_NAME}"
    
    try:
        # Check if already registered
        response = autoscaling.describe_scalable_targets(
            ServiceNamespace="sagemaker",
            ResourceIds=[resource_id]
        )
        
        if response["ScalableTargets"]:
            print(f"✅ Scalable target already registered: {resource_id}")
            return True
    except Exception as e:
        print(f"  ℹ️  Checking registration: {e}")
    
    print(f"📝 Registering scalable target: {resource_id}")
    print(f"   Min capacity: {MIN_CAPACITY}")
    print(f"   Max capacity: {MAX_CAPACITY}")
    
    try:
        autoscaling.register_scalable_target(
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            MinCapacity=MIN_CAPACITY,
            MaxCapacity=MAX_CAPACITY,
            RoleARN=role_arn
        )
        print(f"  ✅ Scalable target registered successfully")
        return True
    except Exception as e:
        print(f"  ❌ Error registering scalable target: {e}")
        return False


def create_scaling_policy() -> bool:
    """Create target tracking scaling policy."""
    resource_id = f"endpoint/{ENDPOINT_NAME}/variant/{VARIANT_NAME}"
    policy_name = "scale-on-invocations"
    
    # Check if policy already exists
    try:
        policies = autoscaling.describe_scaling_policies(
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount"
        )
        
        for policy in policies.get("ScalingPolicies", []):
            if policy["PolicyName"] == policy_name:
                print(f"✅ Scaling policy already exists: {policy_name}")
                return True
    except Exception as e:
        print(f"  ℹ️  Checking existing policies: {e}")
    
    print(f"📝 Creating scaling policy: {policy_name}")
    print(f"   Target: {TARGET_VALUE}% of max invocations per instance")
    
    try:
        autoscaling.put_scaling_policy(
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            ScalableDimension="sagemaker:variant:DesiredInstanceCount",
            PolicyName=policy_name,
            PolicyType="TargetTrackingScaling",
            TargetTrackingScalingPolicyConfiguration={
                "TargetValue": TARGET_VALUE,
                "PredefinedMetricSpecification": {
                    "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
                },
                "ScaleInCooldown": 300,  # 5 minutes before scaling in
                "ScaleOutCooldown": 60   # 1 minute before scaling out
            }
        )
        print(f"  ✅ Scaling policy created successfully")
        return True
    except Exception as e:
        print(f"  ❌ Error creating scaling policy: {e}")
        return False


def verify_endpoint_status():
    """Verify endpoint is in service."""
    try:
        response = sagemaker.describe_endpoint(EndpointName=ENDPOINT_NAME)
        status = response["EndpointStatus"]
        
        if status == "InService":
            print(f"✅ Endpoint is InService: {ENDPOINT_NAME}")
            return True
        else:
            print(f"⚠️  Endpoint status: {status}")
            print(f"   Auto-scaling can only be configured for InService endpoints")
            return False
    except Exception as e:
        print(f"❌ Error checking endpoint: {e}")
        return False


def main():
    print("=" * 70)
    print("SAGEMAKER ENDPOINT AUTO-SCALING SETUP")
    print("=" * 70)
    print()
    print(f"Endpoint: {ENDPOINT_NAME}")
    print(f"Variant: {VARIANT_NAME}")
    print(f"Min Capacity: {MIN_CAPACITY}")
    print(f"Max Capacity: {MAX_CAPACITY}")
    print(f"Target: {TARGET_VALUE}% invocations per instance")
    print()
    
    # Verify endpoint is in service
    if not verify_endpoint_status():
        print("\n❌ Cannot proceed: Endpoint must be InService")
        sys.exit(1)
    
    # Step 1: Create IAM role
    print("\n" + "=" * 70)
    print("STEP 1: Creating IAM Role for Auto-Scaling")
    print("=" * 70)
    role_arn = create_autoscaling_role()
    
    # Step 2: Register scalable target
    print("\n" + "=" * 70)
    print("STEP 2: Registering Scalable Target")
    print("=" * 70)
    if not register_scalable_target(role_arn):
        print("\n❌ Failed to register scalable target")
        sys.exit(1)
    
    # Step 3: Create scaling policy
    print("\n" + "=" * 70)
    print("STEP 3: Creating Scaling Policy")
    print("=" * 70)
    if not create_scaling_policy():
        print("\n❌ Failed to create scaling policy")
        sys.exit(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ AUTO-SCALING SETUP COMPLETE")
    print("=" * 70)
    print()
    print("Configuration:")
    print(f"  • Endpoint: {ENDPOINT_NAME}")
    print(f"  • Min Instances: {MIN_CAPACITY}")
    print(f"  • Max Instances: {MAX_CAPACITY}")
    print(f"  • Scaling Target: {TARGET_VALUE}% invocations per instance")
    print(f"  • Scale Out Cooldown: 60 seconds")
    print(f"  • Scale In Cooldown: 300 seconds (5 minutes)")
    print()
    print("Monitoring:")
    print(f"  • View in AWS Console: Application Auto Scaling → Scalable targets")
    print(f"  • CloudWatch Metrics: AWS/SageMaker → InvocationsPerInstance")
    print()
    print("Cost Estimate:")
    print(f"  • Current: 1 × ml.m5.large = ~$83/month")
    print(f"  • Max: 3 × ml.m5.large = ~$249/month (only during high traffic)")
    print()


if __name__ == "__main__":
    main()

