output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.events.name
}

output "s3_bucket_name" {
  description = "S3 bucket name for data storage"
  value       = aws_s3_bucket.data.id
}

# Reference existing Lambda functions via data sources
output "ingestion_handler_arn" {
  description = "Ingestion Handler Lambda function ARN"
  value       = data.aws_lambda_function.existing_ingestion_handler.arn
}

output "orchestrator_arn" {
  description = "Orchestrator Lambda function ARN"
  value       = data.aws_lambda_function.existing_orchestrator.arn
}

output "ai_analyzer_arn" {
  description = "AI Analyzer Lambda function ARN"
  value       = data.aws_lambda_function.existing_ai_analyzer.arn
}

output "decision_combiner_arn" {
  description = "Decision Combiner Lambda function ARN"
  value       = data.aws_lambda_function.existing_decision_combiner.arn
}

output "honeypot_arn" {
  description = "Honeypot Lambda function ARN"
  value       = data.aws_lambda_function.existing_honeypot.arn
}

output "sagemaker_execution_role_arn" {
  description = "SageMaker Execution Role ARN"
  value       = aws_iam_role.sagemaker_execution.arn
}

output "sagemaker_execution_role_name" {
  description = "SageMaker Execution Role Name"
  value       = aws_iam_role.sagemaker_execution.name
}
