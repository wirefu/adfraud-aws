# SageMaker Execution Role
# IAM role for SageMaker to access S3, create endpoints, and run training jobs

resource "aws_iam_role" "sagemaker_execution" {
  name = "${var.stack_name}-sagemaker-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "sagemaker.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Environment = var.environment
    Project     = "FraudGuardAI"
    ManagedBy   = "Terraform"
  }
}

# Attach managed policy for SageMaker full access
resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# S3 access policy for DataBucket
resource "aws_iam_role_policy" "sagemaker_s3_access" {
  name = "S3Access"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ]
      Resource = [
        "${aws_s3_bucket.data.arn}/*",
        aws_s3_bucket.data.arn
      ]
    }]
  })
}

# CloudWatch Logs access for SageMaker operations
resource "aws_iam_role_policy" "sagemaker_cloudwatch_logs" {
  name = "CloudWatchLogsAccess"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ]
      Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/sagemaker/*"
    }]
  })
}
