#!/bin/bash
# Update Lambda function to use Google Ads layer
# This script updates the Lambda function configuration to use the layer

set -e

FUNCTION_NAME="${1:-fraudguard-ai-dev-GoogleAdsIngestion}"
LAYER_NAME="${2:-google-ads-dependencies}"
REGION="${AWS_REGION:-us-east-1}"

echo "=== Updating Lambda Function with Layer ==="
echo "Function: $FUNCTION_NAME"
echo "Layer: $LAYER_NAME"
echo "Region: $REGION"
echo ""

# Get latest layer version
echo "Getting latest layer version..."
LAYER_ARN=$(aws lambda list-layer-versions \
    --layer-name "$LAYER_NAME" \
    --region "$REGION" \
    --query 'LayerVersions[0].LayerVersionArn' \
    --output text)

if [ "$LAYER_ARN" == "None" ] || [ -z "$LAYER_ARN" ]; then
    echo "ERROR: Layer '$LAYER_NAME' not found in region $REGION"
    echo "Please publish the layer first using ./scripts/publish-google-ads-layer.sh"
    exit 1
fi

echo "Layer ARN: $LAYER_ARN"
echo ""

# Get current layers
echo "Getting current function configuration..."
CURRENT_LAYERS=$(aws lambda get-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Layers[*].Arn' \
    --output text)

# Update function with layer
echo "Updating Lambda function..."
if [ -n "$CURRENT_LAYERS" ] && [ "$CURRENT_LAYERS" != "None" ]; then
    # Append to existing layers
    LAYERS="$CURRENT_LAYERS $LAYER_ARN"
else
    # First layer
    LAYERS="$LAYER_ARN"
fi

aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --layers $LAYERS \
    --region "$REGION" \
    --output json > /tmp/lambda-update.json

echo ""
echo "=== Lambda Function Updated ==="
echo "Function: $FUNCTION_NAME"
echo "Layers:"
echo "$LAYERS" | tr ' ' '\n' | sed 's/^/  - /'
echo ""
echo "Function configuration saved to: /tmp/lambda-update.json"

