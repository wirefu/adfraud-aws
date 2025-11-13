variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "stack_name" {
  description = "Stack name prefix for resources"
  type        = string
  default     = "fraudguard-ai"
}

variable "create_dynamodb_table" {
  description = "Whether to create the DynamoDB table"
  type        = bool
  default     = true
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name (used if create_dynamodb_table is false)"
  type        = string
  default     = "fraudguard-events-dev"
}
