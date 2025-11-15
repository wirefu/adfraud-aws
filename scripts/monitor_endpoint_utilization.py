#!/usr/bin/env python3
"""
Monitor SageMaker endpoint utilization and auto-scaling activity.

This script provides insights into:
- Current instance count
- Invocations per instance
- Auto-scaling events
- Cost estimates
"""

import boto3
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
ENDPOINT_NAME = "fraudguard-xgboost-endpoint"
VARIANT_NAME = "AllTraffic"
REGION = "us-east-1"

# Cost per hour (ml.m5.large)
INSTANCE_COST_PER_HOUR = 0.115

# AWS Clients
cloudwatch = boto3.client("cloudwatch", region_name=REGION)
sagemaker = boto3.client("sagemaker", region_name=REGION)
autoscaling = boto3.client("application-autoscaling", region_name=REGION)


def get_endpoint_info() -> Dict[str, Any]:
    """Get current endpoint information."""
    try:
        response = sagemaker.describe_endpoint(EndpointName=ENDPOINT_NAME)
        return {
            "status": response["EndpointStatus"],
            "config_name": response["EndpointConfigName"],
            "creation_time": response["CreationTime"]
        }
    except Exception as e:
        print(f"❌ Error getting endpoint info: {e}")
        return {}


def get_current_instance_count() -> int:
    """Get current desired instance count from CloudWatch."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=5)
        
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/SageMaker",
            MetricName="DesiredInstanceCount",
            Dimensions=[
                {"Name": "EndpointName", "Value": ENDPOINT_NAME},
                {"Name": "VariantName", "Value": VARIANT_NAME}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Average"]
        )
        
        if response["Datapoints"]:
            # Get most recent datapoint
            latest = max(response["Datapoints"], key=lambda x: x["Timestamp"])
            return int(latest["Average"])
        return 1  # Default
    except Exception as e:
        print(f"⚠️  Could not get instance count: {e}")
        return 1


def get_invocations_per_instance() -> float:
    """Get average invocations per instance."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        # Get total invocations
        invocations_response = cloudwatch.get_metric_statistics(
            Namespace="AWS/SageMaker",
            MetricName="Invocations",
            Dimensions=[
                {"Name": "EndpointName", "Value": ENDPOINT_NAME},
                {"Name": "VariantName", "Value": VARIANT_NAME}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Sum"]
        )
        
        # Get instance count
        instance_response = cloudwatch.get_metric_statistics(
            Namespace="AWS/SageMaker",
            MetricName="DesiredInstanceCount",
            Dimensions=[
                {"Name": "EndpointName", "Value": ENDPOINT_NAME},
                {"Name": "VariantName", "Value": VARIANT_NAME}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Average"]
        )
        
        if invocations_response["Datapoints"] and instance_response["Datapoints"]:
            total_invocations = sum(dp["Sum"] for dp in invocations_response["Datapoints"])
            avg_instances = sum(dp["Average"] for dp in instance_response["Datapoints"]) / len(instance_response["Datapoints"])
            
            if avg_instances > 0:
                return total_invocations / avg_instances
        return 0.0
    except Exception as e:
        print(f"⚠️  Could not calculate invocations per instance: {e}")
        return 0.0


def get_autoscaling_activity() -> list:
    """Get recent auto-scaling activity."""
    resource_id = f"endpoint/{ENDPOINT_NAME}/variant/{VARIANT_NAME}"
    
    try:
        response = autoscaling.describe_scaling_activities(
            ServiceNamespace="sagemaker",
            ResourceId=resource_id,
            MaxResults=10
        )
        return response.get("ScalingActivities", [])
    except Exception as e:
        print(f"⚠️  Could not get scaling activity: {e}")
        return []


def estimate_monthly_cost(instance_count: int) -> Dict[str, float]:
    """Estimate monthly cost based on instance count."""
    hourly_cost = instance_count * INSTANCE_COST_PER_HOUR
    daily_cost = hourly_cost * 24
    monthly_cost = daily_cost * 30
    
    return {
        "hourly": hourly_cost,
        "daily": daily_cost,
        "monthly": monthly_cost
    }


def main():
    print("=" * 70)
    print("SAGEMAKER ENDPOINT UTILIZATION MONITOR")
    print("=" * 70)
    print()
    
    # Get endpoint info
    endpoint_info = get_endpoint_info()
    if endpoint_info:
        print(f"Endpoint: {ENDPOINT_NAME}")
        print(f"Status: {endpoint_info.get('status', 'Unknown')}")
        print()
    
    # Current instance count
    instance_count = get_current_instance_count()
    print(f"Current Instance Count: {instance_count}")
    
    # Cost estimate
    costs = estimate_monthly_cost(instance_count)
    print()
    print("Cost Estimates:")
    print(f"  • Hourly: ${costs['hourly']:.3f}")
    print(f"  • Daily: ${costs['daily']:.2f}")
    print(f"  • Monthly: ${costs['monthly']:.2f}")
    
    # Invocations per instance
    invocations_per_instance = get_invocations_per_instance()
    print()
    print(f"Average Invocations Per Instance (last hour): {invocations_per_instance:.1f}")
    print(f"Target: 70% of max (auto-scaling threshold)")
    
    # Auto-scaling activity
    activities = get_autoscaling_activity()
    if activities:
        print()
        print("Recent Auto-Scaling Activity:")
        for activity in activities[:5]:  # Show last 5
            status = activity.get("StatusCode", "Unknown")
            description = activity.get("Description", "No description")
            timestamp = activity.get("StartTime", datetime.utcnow())
            print(f"  • {timestamp.strftime('%Y-%m-%d %H:%M:%S')}: {status}")
            print(f"    {description}")
    else:
        print()
        print("No recent auto-scaling activity")
    
    # Recommendations
    print()
    print("=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if instance_count == 1:
        print("✅ Current configuration is cost-optimized")
        print("   Endpoint will scale up automatically if traffic increases")
    elif instance_count == 3:
        print("⚠️  Endpoint at maximum capacity (3 instances)")
        print("   Consider:")
        print("   - Upgrading instance type if consistently at max")
        print("   - Reviewing traffic patterns")
        print("   - Optimizing model inference time")
    else:
        print(f"ℹ️  Endpoint scaled to {instance_count} instances")
        print("   Auto-scaling is working as expected")
    
    if invocations_per_instance > 1000:
        print()
        print("⚠️  High invocations per instance detected")
        print("   Endpoint may scale up soon")
    
    print()


if __name__ == "__main__":
    main()

