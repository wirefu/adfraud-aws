#!/bin/bash
# Build Google Ads Lambda Layer
# This script builds a Lambda layer with Google Ads dependencies using Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAYER_NAME="google-ads-dependencies"
LAYER_DIR="$PROJECT_ROOT/build/layers/$LAYER_NAME"
PYTHON_VERSION="3.11"
REGION="${AWS_REGION:-us-east-1}"

echo "=== Building Google Ads Lambda Layer ==="
echo "Layer name: $LAYER_NAME"
echo "Python version: $PYTHON_VERSION"
echo "Region: $REGION"
echo ""

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$LAYER_DIR"
mkdir -p "$LAYER_DIR/python"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH"
    echo "Please install Docker to build Lambda layers with native dependencies"
    exit 1
fi

echo "Building layer using Docker (Lambda Python $PYTHON_VERSION base image)..."
echo "This may take a few minutes..."

# Build layer using Docker with Lambda Python base image
docker run --rm \
    -v "$PROJECT_ROOT:/var/task" \
    -w /var/task \
    public.ecr.aws/lambda/python:$PYTHON_VERSION \
    /bin/bash -c "
        echo 'Installing Google Ads dependencies...'
        pip install --no-cache-dir google-ads -t build/layers/$LAYER_NAME/python/
        
        echo 'Cleaning up unnecessary files...'
        find build/layers/$LAYER_NAME/python -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
        find build/layers/$LAYER_NAME/python -type d -name '*.dist-info' -exec rm -rf {} + 2>/dev/null || true
        find build/layers/$LAYER_NAME/python -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
        
        echo 'Calculating layer size...'
        du -sh build/layers/$LAYER_NAME/python/
    "

# Create layer zip
echo ""
echo "Creating layer zip file..."
cd "$LAYER_DIR"
zip -r "../${LAYER_NAME}.zip" . -q
cd "$PROJECT_ROOT"

LAYER_ZIP="$PROJECT_ROOT/build/layers/${LAYER_NAME}.zip"
LAYER_SIZE=$(du -h "$LAYER_ZIP" | cut -f1)

echo "Layer zip created: $LAYER_ZIP"
echo "Layer size: $LAYER_SIZE"

# Check layer size (Lambda limit is 50MB zipped, 250MB unzipped)
LAYER_SIZE_BYTES=$(stat -f%z "$LAYER_ZIP" 2>/dev/null || stat -c%s "$LAYER_ZIP" 2>/dev/null)
LAYER_SIZE_MB=$((LAYER_SIZE_BYTES / 1024 / 1024))

if [ $LAYER_SIZE_MB -gt 50 ]; then
    echo ""
    echo "WARNING: Layer size ($LAYER_SIZE_MB MB) exceeds Lambda's 50MB zipped limit!"
    echo "You may need to split into multiple layers or optimize dependencies"
    exit 1
fi

echo ""
echo "=== Layer Build Complete ==="
echo "Layer zip: $LAYER_ZIP"
echo "Size: $LAYER_SIZE ($LAYER_SIZE_MB MB)"
echo ""
echo "Next steps:"
echo "1. Publish the layer:"
echo "   aws lambda publish-layer-version \\"
echo "     --layer-name $LAYER_NAME \\"
echo "     --zip-file fileb://$LAYER_ZIP \\"
echo "     --compatible-runtimes python$PYTHON_VERSION \\"
echo "     --region $REGION"
echo ""
echo "2. Update Lambda function to use the layer:"
echo "   aws lambda update-function-configuration \\"
echo "     --function-name fraudguard-ai-dev-GoogleAdsIngestion \\"
echo "     --layers <layer-arn> \\"
echo "     --region $REGION"

