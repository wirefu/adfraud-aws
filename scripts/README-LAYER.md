# Google Ads Lambda Layer Setup

This guide explains how to set up and use the Google Ads Lambda layer for the ingestion function.

## Quick Start

```bash
# 1. Build the layer
./scripts/build-google-ads-layer.sh

# 2. Publish to AWS
./scripts/publish-google-ads-layer.sh

# 3. Update Lambda function
./scripts/update-lambda-with-layer.sh

# 4. Rebuild function package (code only)
./scripts/rebuild-function-package.sh google_ads_ingestion
```

## Prerequisites

- **Docker**: Required for building Linux-compatible dependencies
- **AWS CLI**: Configured with appropriate credentials
- **Permissions**: IAM permissions to create Lambda layers and update functions

## Detailed Steps

### 1. Build Layer

The build script uses Docker to ensure dependencies are compiled for Lambda's Linux environment:

```bash
./scripts/build-google-ads-layer.sh
```

**What it does:**
- Creates layer directory structure (`build/layers/google-ads-dependencies/python/`)
- Uses Docker with Lambda Python 3.11 base image
- Installs `google-ads` library and all dependencies
- Cleans up unnecessary files (__pycache__, .dist-info, etc.)
- Creates layer zip file
- Validates size (< 50MB zipped limit)

**Output:**
- Layer zip: `build/layers/google-ads-dependencies.zip`
- Size validation

### 2. Publish Layer

Publishes the layer to AWS Lambda:

```bash
./scripts/publish-google-ads-layer.sh
```

**What it does:**
- Validates layer zip exists
- Publishes layer to AWS Lambda
- Creates new layer version
- Outputs layer ARN

**Output:**
- Layer ARN (save this for function configuration)
- Layer version number

### 3. Update Lambda Function

Attaches the layer to the Lambda function:

```bash
./scripts/update-lambda-with-layer.sh
```

Or specify function name:

```bash
./scripts/update-lambda-with-layer.sh fraudguard-ai-dev-GoogleAdsIngestion
```

**What it does:**
- Gets latest layer version ARN
- Updates Lambda function configuration
- Attaches layer to function

### 4. Rebuild Function Package

Since dependencies are in the layer, rebuild the function package with code only:

```bash
# Create function package (code only)
mkdir -p build/google_ads_ingestion
cp -r src/google_ads_ingestion/* build/google_ads_ingestion/
cd build/google_ads_ingestion
zip -r ../google_ads_ingestion.zip . -x "*.pyc" -x "__pycache__/*"

# Upload and update
aws s3 cp build/google_ads_ingestion.zip \
  s3://fraudguard-ai-dev-data-971422717446/lambda-packages/google_ads_ingestion.zip \
  --region us-east-1

aws lambda update-function-code \
  --function-name fraudguard-ai-dev-GoogleAdsIngestion \
  --s3-bucket fraudguard-ai-dev-data-971422717446 \
  --s3-key lambda-packages/google_ads_ingestion.zip \
  --region us-east-1
```

## Layer Management

### List Layer Versions

```bash
aws lambda list-layer-versions \
  --layer-name google-ads-dependencies \
  --region us-east-1
```

### Get Layer Details

```bash
aws lambda get-layer-version \
  --layer-name google-ads-dependencies \
  --version-number <version> \
  --region us-east-1
```

### Delete Layer Version

```bash
aws lambda delete-layer-version \
  --layer-name google-ads-dependencies \
  --version-number <version> \
  --region us-east-1
```

## Troubleshooting

### Docker Not Available

If Docker is not installed, you can:

1. **Install Docker Desktop** (macOS/Windows)
2. **Use EC2 Linux instance** to build the layer
3. **Use GitHub Actions** with Docker runner

### Layer Size Too Large

If layer exceeds 50MB zipped:
- Split into multiple layers (e.g., `google-ads-core`, `google-ads-extras`)
- Remove unnecessary dependencies
- Use Lambda container images instead

### Function Still Can't Import

After attaching layer:
1. Verify layer is attached: `aws lambda get-function-configuration --function-name <name>`
2. Check layer ARN matches published version
3. Verify Python runtime matches (3.11)
4. Check CloudWatch logs for import errors

## Updating Dependencies

To update Google Ads library version:

1. Update `src/google_ads_ingestion/requirements.txt`
2. Rebuild layer: `./scripts/build-google-ads-layer.sh`
3. Publish new version: `./scripts/publish-google-ads-layer.sh`
4. Update function to use new layer version: `./scripts/update-lambda-with-layer.sh`

## Using Layer in Other Functions

To use the same layer in other Lambda functions:

```bash
# Get layer ARN
LAYER_ARN=$(aws lambda list-layer-versions \
  --layer-name google-ads-dependencies \
  --region us-east-1 \
  --query 'LayerVersions[0].LayerVersionArn' \
  --output text)

# Attach to function
aws lambda update-function-configuration \
  --function-name <other-function-name> \
  --layers $LAYER_ARN \
  --region us-east-1
```

