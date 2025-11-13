# Existing DynamoDB Table - Import and add missing GSIs
resource "aws_dynamodb_table" "events" {
  name             = "fraudguard-events-dev"
  billing_mode     = "PAY_PER_REQUEST"
  hash_key         = "event_id"
  # Note: Table currently has no range key, but timestamp is used in GSIs

  # Existing attributes (must match what's in the table)
  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  attribute {
    name = "campaign_id"
    type = "S"
  }

  attribute {
    name = "device_id"
    type = "S"
  }

  # Additional attributes for new GSIs
  # These may already exist in items but need to be in AttributeDefinitions for GSIs
  attribute {
    name = "gclid"
    type = "S"
  }

  attribute {
    name = "keyword"
    type = "S"
  }

  attribute {
    name = "target_id"
    type = "S"
  }

  # Existing GSIs (must be included to match current state)
  global_secondary_index {
    name            = "campaign-timestamp-index"
    hash_key        = "campaign_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "device-timestamp-index"
    hash_key        = "device_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # NEW GSIs to be added (these will be created by Terraform)
  global_secondary_index {
    name            = "gclid-timestamp-index"
    hash_key        = "gclid"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "keyword-timestamp-index"
    hash_key        = "keyword"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "target-timestamp-index"
    hash_key        = "target_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # TTL and streams not currently enabled, but can be added if needed
  # ttl {
  #   attribute_name = "ttl"
  #   enabled        = true
  # }

  # stream_enabled   = true
  # stream_view_type = "NEW_AND_OLD_IMAGES"

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Environment = var.environment
    Project     = "FraudGuardAI"
    ManagedBy   = "Terraform"
  }
}



# S3 Bucket (already imported)
resource "aws_s3_bucket" "data" {
  bucket = "${var.stack_name}-data-${data.aws_caller_identity.current.account_id}"

  tags = {
    Environment = var.environment
    Project     = "FraudGuardAI"
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "ArchiveOldData"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "DeleteOldVersions"
    status = "Enabled"
    filter {}
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER_IR"
    }
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket = aws_s3_bucket.data.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DenyInsecureConnections"
      Effect = "Deny"
      Principal = "*"
      Action = "s3:*"
      Resource = [
        "${aws_s3_bucket.data.arn}/*",
        aws_s3_bucket.data.arn
      ]
      Condition = {
        Bool = {
          "aws:SecureTransport" = "false"
        }
      }
    }]
  })
}

# Note: Lambda functions and IAM roles are managed by CloudFormation
# We reference them via data sources but don't manage them with Terraform
# This allows us to see them in outputs and reference them if needed
