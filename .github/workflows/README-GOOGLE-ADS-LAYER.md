# Google Ads Lambda Layer Deployment Workflow

This document explains the GitHub Actions workflow for building and deploying the Google Ads Lambda layer.

## Overview

The `deploy-google-ads-layer.yml` workflow automatically:
1. Builds a Lambda layer with Google Ads dependencies using Docker
2. Publishes the layer to AWS Lambda
3. Updates the Lambda function to use the layer
4. Rebuilds the function package (code only, no dependencies)
5. Updates the Lambda function code

## Workflow Triggers

### Automatic Deployment

The workflow runs automatically when:
- Code is pushed to `main` or `develop` branches
- Changes are made to files in `src/google_ads_ingestion/`
- Changes are made to layer build scripts
- The workflow file itself is updated

### Manual Deployment

You can manually trigger the workflow:
1. Go to GitHub Actions tab
2. Select "Deploy Google Ads Lambda Layer" workflow
3. Click "Run workflow"
4. Choose the environment (dev, staging, prod)
5. Optionally check "Rebuild layer (even if no changes)"
6. Click "Run workflow"

## Workflow Steps

### 1. Set Environment Variables
- Determines deployment environment (dev/staging/prod)
- Sets environment-specific values:
  - Function name
  - S3 bucket name
  - DynamoDB table name

### 2. Checkout Code
- Checks out the repository code

### 3. Configure AWS Credentials
- Configures AWS credentials from GitHub secrets
- Required secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### 4. Build Lambda Layer
- Uses Docker with Lambda Python 3.11 base image
- Installs Google Ads dependencies
- Cleans up unnecessary files
- Creates layer zip file
- Validates layer size (< 50MB zipped)

### 5. Publish Lambda Layer
- Publishes layer to AWS Lambda
- Creates new layer version
- Outputs layer ARN and version

### 6. Update Lambda Function with Layer
- Gets current function configuration
- Attaches layer to function
- Updates function configuration

### 7. Rebuild Function Package (Code Only)
- Creates function package without dependencies
- Excludes cache files and unnecessary files
- Creates zip file

### 8. Upload Function Package to S3
- Uploads function package to S3
- Uses path: `s3://<bucket>/lambda-packages/google_ads_ingestion.zip`

### 9. Update Lambda Function Code
- Updates Lambda function code from S3
- Uses the uploaded function package

### 10. Wait for Function Update
- Waits for Lambda function update to complete
- Ensures function is ready before next steps

### 11. Output Deployment Summary
- Creates deployment summary in GitHub Actions
- Displays layer and function information
- Provides next steps for testing

## Configuration

### Environment Variables

The workflow uses these environment variables:

- `AWS_REGION`: AWS region (default: `us-east-1`)
- `PYTHON_VERSION`: Python version (default: `3.11`)
- `LAYER_NAME`: Lambda layer name (default: `google-ads-dependencies`)

### Environment-Specific Configuration

Each environment has different resource names:

**Dev:**
- Function: `fraudguard-ai-dev-GoogleAdsIngestion`
- S3 Bucket: `fraudguard-ai-dev-data-971422717446`
- Table: `google-ads-metrics-dev`

**Staging:**
- Function: `fraudguard-ai-staging-GoogleAdsIngestion`
- S3 Bucket: `fraudguard-ai-staging-data-971422717446`
- Table: `google-ads-metrics-staging`

**Prod:**
- Function: `fraudguard-ai-prod-GoogleAdsIngestion`
- S3 Bucket: `fraudguard-ai-prod-data-971422717446`
- Table: `google-ads-metrics-prod`

### Required GitHub Secrets

1. **AWS_ACCESS_KEY_ID**: AWS access key ID
2. **AWS_SECRET_ACCESS_KEY**: AWS secret access key

### Required AWS Resources

1. **Lambda Function**: Must exist before first deployment
2. **S3 Bucket**: Must exist for function package storage
3. **IAM Permissions**: The AWS credentials need:
   - `lambda:PublishLayerVersion`
   - `lambda:GetLayerVersion`
   - `lambda:UpdateFunctionConfiguration`
   - `lambda:UpdateFunctionCode`
   - `lambda:GetFunctionConfiguration`
   - `s3:PutObject`
   - `s3:GetObject`

## Setup Instructions

### 1. Configure GitHub Secrets

Go to GitHub repository → Settings → Secrets and variables → Actions:

1. Add `AWS_ACCESS_KEY_ID`
2. Add `AWS_SECRET_ACCESS_KEY`

### 2. Create IAM User/Role

Create an IAM user or role with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:PublishLayerVersion",
        "lambda:GetLayerVersion",
        "lambda:ListLayerVersions",
        "lambda:UpdateFunctionConfiguration",
        "lambda:UpdateFunctionCode",
        "lambda:GetFunctionConfiguration",
        "lambda:GetFunction",
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. Ensure Lambda Function Exists

The Lambda function must exist before the workflow can update it. If it doesn't exist, create it first:

```bash
# Create function (if not exists)
aws lambda create-function \
  --function-name fraudguard-ai-dev-GoogleAdsIngestion \
  --runtime python3.11 \
  --role <role-arn> \
  --handler app.lambda_handler \
  --code S3Bucket=<bucket>,S3Key=<key> \
  --region us-east-1
```

## Testing

After deployment, test the Lambda function:

```bash
# Test the function
aws lambda invoke \
  --function-name fraudguard-ai-dev-GoogleAdsIngestion \
  --payload '{}' \
  --region us-east-1 \
  /tmp/lambda-response.json

# Check response
cat /tmp/lambda-response.json | jq

# Check logs
aws logs tail /aws/lambda/fraudguard-ai-dev-GoogleAdsIngestion --follow --region us-east-1
```

## Troubleshooting

### Layer Build Fails

- **Docker not available**: GitHub Actions runners have Docker pre-installed
- **Layer too large**: Check layer size, may need to split into multiple layers
- **Dependencies fail to install**: Check Google Ads library version compatibility

### Layer Publish Fails

- **IAM permissions**: Ensure AWS credentials have `lambda:PublishLayerVersion` permission
- **Layer name conflict**: Layer name may already exist, check existing layers

### Function Update Fails

- **Function doesn't exist**: Create function first before running workflow
- **IAM permissions**: Ensure AWS credentials have `lambda:UpdateFunctionConfiguration` permission
- **S3 upload fails**: Check S3 bucket exists and credentials have `s3:PutObject` permission

### Function Can't Import Dependencies

- **Layer not attached**: Check function configuration, ensure layer is attached
- **Layer version mismatch**: Ensure function uses correct layer version
- **Python runtime mismatch**: Ensure function uses Python 3.11 runtime

## Updating Dependencies

To update Google Ads library version:

1. Update `src/google_ads_ingestion/requirements.txt`
2. Push changes to trigger workflow
3. Or manually trigger workflow with "Rebuild layer" option

## Monitoring

Monitor the deployment:

1. **GitHub Actions**: Check workflow run status
2. **CloudWatch Logs**: Check Lambda function logs
3. **Lambda Metrics**: Check function invocation metrics

## Best Practices

1. **Version Control**: Always commit workflow changes
2. **Testing**: Test in dev environment before staging/prod
3. **Monitoring**: Monitor CloudWatch logs after deployment
4. **Rollback**: Keep previous layer versions for rollback
5. **Documentation**: Update this README when workflow changes

