#!/bin/bash
# Publish Google Ads Lambda Layer to AWS
# This script publishes the built layer to AWS Lambda

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAYER_NAME="google-ads-dependencies"
LAYER_ZIP="$PROJECT_ROOT/build/layers/${LAYER_NAME}.zip"
PYTHON_VERSION="3.11"
REGION="${AWS_REGION:-us-east-1}"

echo "=== Publishing Google Ads Lambda Layer ==="
echo "Layer name: $LAYER_NAME"
echo "Layer zip: $LAYER_ZIP"
echo "Region: $REGION"
echo ""

# Check if layer zip exists
if [ ! -f "$LAYER_ZIP" ]; then
    echo "ERROR: Layer zip not found: $LAYER_ZIP"
    echo "Please run ./scripts/build-google-ads-layer.sh first"
    exit 1
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI is not installed or not in PATH"
    exit 1
fi

# Publish layer
echo "Publishing layer to AWS Lambda..."
LAYER_VERSION=$(aws lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --zip-file "fileb://$LAYER_ZIP" \
    --compatible-runtimes "python$PYTHON_VERSION" \
    --description "Google Ads API dependencies for Lambda functions" \
    --region "$REGION" \
    --query 'Version' \
    --output text)

LAYER_ARN=$(aws lambda get-layer-version \
    --layer-name "$LAYER_NAME" \
    --version-number "$LAYER_VERSION" \
    --region "$REGION" \
    --query 'LayerVersionArn' \
    --output text)

echo ""
echo "=== Layer Published Successfully ==="
echo "Layer ARN: $LAYER_ARN"
echo "Version: $LAYER_VERSION"
echo ""
echo "Layer ARN (save this for Lambda function configuration):"
echo "$LAYER_ARN"
echo ""
echo "To update the Lambda function to use this layer:"
echo "aws lambda update-function-configuration \\"
echo "  --function-name fraudguard-ai-dev-GoogleAdsIngestion \\"
echo "  --layers $LAYER_ARN \\"
echo "  --region $REGION"

