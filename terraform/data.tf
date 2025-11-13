# Data sources for existing resources

# Existing DynamoDB Table
data "aws_dynamodb_table" "existing_events" {
  name = "fraudguard-events-dev"
}

# Existing Lambda Functions
data "aws_lambda_function" "existing_ingestion_handler" {
  function_name = "fraudguard-ai-ingestion-handler"
}

data "aws_lambda_function" "existing_orchestrator" {
  function_name = "fraudguard-ai-orchestrator"
}

data "aws_lambda_function" "existing_ai_analyzer" {
  function_name = "fraudguard-ai-ai-analyzer"
}

data "aws_lambda_function" "existing_decision_combiner" {
  function_name = "fraudguard-ai-decision-combiner"
}

data "aws_lambda_function" "existing_honeypot" {
  function_name = "fraudguard-ai-honeypot"
}

# Existing IAM Roles
data "aws_iam_role" "existing_ingestion_handler_role" {
  name = "fraudguard-ai-IngestionHandlerRole-znlfQeLxomxF"
}

data "aws_iam_role" "existing_orchestrator_role" {
  name = "fraudguard-ai-FraudOrchestratorRole-oFPS99y2YsLm"
}

data "aws_iam_role" "existing_ai_analyzer_role" {
  name = "fraudguard-ai-AIAnalyzerRole-5MQCC15u0aa6"
}

data "aws_iam_role" "existing_decision_combiner_role" {
  name = "fraudguard-ai-DecisionCombinerRole-pbRjQV8V0IUn"
}

data "aws_iam_role" "existing_honeypot_role" {
  name = "fraudguard-ai-HoneypotFunctionRole-qd95QAiF1c4F"
}
