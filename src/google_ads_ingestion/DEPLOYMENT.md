# Google Ads Ingestion Lambda Deployment Guide

## Issue: Google Ads Library Native Dependencies

The `google-ads` library requires native dependencies (`grpcio`) that must be compiled for Lambda's Linux environment. Building on macOS will result in import errors.

## Solution: Lambda Layer (Recommended)

We use a **Lambda Layer** to provide Google Ads dependencies. This approach:
- ✅ Reusable across multiple Lambda functions
- ✅ Faster deployments (only update function code)
- ✅ Better separation of dependencies and code
- ✅ Easier to maintain and update

### Step 1: Build the Lambda Layer

Build the layer using Docker (ensures Linux-compatible dependencies):

```bash
./scripts/build-google-ads-layer.sh
```

This script:
- Uses Docker with Lambda Python 3.11 base image
- Installs Google Ads dependencies
- Creates a layer zip file
- Validates layer size (must be < 50MB zipped)

**Prerequisites:**
- Docker installed and running
- AWS CLI configured

### Step 2: Publish the Layer to AWS

Publish the built layer to AWS Lambda:

```bash
./scripts/publish-google-ads-layer.sh
```

This will:
- Upload the layer to AWS Lambda
- Create a new layer version
- Output the layer ARN for use in Lambda functions

### Step 3: Update Lambda Function to Use Layer

Attach the layer to your Lambda function:

```bash
./scripts/update-lambda-with-layer.sh
```

Or manually:

```bash
# Get the layer ARN from Step 2, then:
aws lambda update-function-configuration \
  --function-name fraudguard-ai-dev-GoogleAdsIngestion \
  --layers <layer-arn> \
  --region us-east-1
```

### Step 4: Rebuild Function Package (Without Dependencies)

Since dependencies are in the layer, rebuild the function package without them:

```bash
# Build function package (code only, no dependencies)
mkdir -p build/google_ads_ingestion
cp -r src/google_ads_ingestion/* build/google_ads_ingestion/
cd build/google_ads_ingestion
zip -r ../google_ads_ingestion.zip . -x "*.pyc" -x "__pycache__/*"

# Upload to S3
aws s3 cp build/google_ads_ingestion.zip \
  s3://fraudguard-ai-dev-data-971422717446/lambda-packages/google_ads_ingestion.zip \
  --region us-east-1

# Update Lambda function code
aws lambda update-function-code \
  --function-name fraudguard-ai-dev-GoogleAdsIngestion \
  --s3-bucket fraudguard-ai-dev-data-971422717446 \
  --s3-key lambda-packages/google_ads_ingestion.zip \
  --region us-east-1
```

## Current Deployment Status

- ✅ Lambda function created: `fraudguard-ai-dev-GoogleAdsIngestion`
- ✅ IAM role created: `fraudguard-ai-dev-GoogleAdsIngestionRole`
- ✅ EventBridge rule configured: `fraudguard-ai-dev-daily-ingestion`
- ⚠️ Package needs to be rebuilt on Linux for native dependencies

## Environment Variables

- `GOOGLE_ADS_METRICS_TABLE_NAME`: `google-ads-metrics-dev`
- `S3_BUCKET_NAME`: `fraudguard-ai-dev-data-971422717446`
- `GOOGLE_ADS_SECRETS_NAME`: `fraudguard-ai-dev-google-ads-api-credentials`
- `GOOGLE_ADS_CUSTOMER_IDS`: (optional) Comma-separated list of customer IDs

## Testing

Once the package is rebuilt on Linux:

```bash
# Test the function
aws lambda invoke \
  --function-name fraudguard-ai-dev-GoogleAdsIngestion \
  --payload '{}' \
  --region us-east-1 \
  /tmp/lambda-response.json

# Check logs
aws logs tail /aws/lambda/fraudguard-ai-dev-GoogleAdsIngestion --follow --region us-east-1
```

