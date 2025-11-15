# IAM Policy for Lambda Orchestrator to Invoke SageMaker Endpoint
# This adds the sagemaker:InvokeEndpoint permission to the Lambda execution role

resource "aws_iam_role_policy" "orchestrator_sagemaker_invoke" {
  name = "SageMakerInvokeEndpointPolicy"
  role = "fraudguard-ai-lambda-execution-role-dev"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sagemaker:InvokeEndpoint"
        Resource = "arn:aws:sagemaker:us-east-1:971422717446:endpoint/*"
      }
    ]
  })
}
