# Auto-Scaling Configuration for SageMaker Endpoint
# This enables automatic scaling of the endpoint based on traffic

# IAM Role for Application Auto Scaling
resource "aws_iam_role" "sagemaker_autoscaling" {
  name = "fraudguard-ai-autoscaling-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "application-autoscaling.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = "FraudGuardAI"
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}

# IAM Policy for Auto-Scaling
resource "aws_iam_role_policy" "sagemaker_autoscaling" {
  name = "SageMakerEndpointAutoScalingPolicy"
  role = aws_iam_role.sagemaker_autoscaling.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:DescribeEndpoint",
          "sagemaker:DescribeEndpointConfig",
          "sagemaker:UpdateEndpointWeightsAndCapacities",
          "sagemaker:DescribeModel",
          "cloudwatch:PutMetricAlarm",
          "cloudwatch:DescribeAlarms",
          "cloudwatch:DeleteAlarms",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:SetAlarmState"
        ]
        Resource = "*"
      }
    ]
  })
}

# Register endpoint as scalable target
resource "aws_appautoscaling_target" "sagemaker_endpoint" {
  max_capacity       = 3
  min_capacity       = 1
  resource_id        = "endpoint/fraudguard-xgboost-endpoint/variant/AllTraffic"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace = "sagemaker"
  role_arn           = aws_iam_role.sagemaker_autoscaling.arn
}

# Target tracking scaling policy
resource "aws_appautoscaling_policy" "sagemaker_endpoint_scaling" {
  name               = "scale-on-invocations"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker_endpoint.resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker_endpoint.scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker_endpoint.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 70.0

    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }

    scale_in_cooldown  = 300  # 5 minutes before scaling in
    scale_out_cooldown = 60   # 1 minute before scaling out
  }
}

# Outputs
output "sagemaker_autoscaling_role_arn" {
  description = "ARN of the IAM role for SageMaker endpoint auto-scaling"
  value       = aws_iam_role.sagemaker_autoscaling.arn
}
