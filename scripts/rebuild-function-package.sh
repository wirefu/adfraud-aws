#!/bin/bash
# Rebuild Lambda function package (code only, no dependencies)
# Usage: ./scripts/rebuild-function-package.sh <function-name>

set -e

FUNCTION_NAME="${1:-google_ads_ingestion}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/$FUNCTION_NAME"
FUNCTION_SRC="$PROJECT_ROOT/src/$FUNCTION_NAME"
ZIP_FILE="$PROJECT_ROOT/build/${FUNCTION_NAME}.zip"
S3_BUCKET="${S3_BUCKET:-fraudguard-ai-dev-data-971422717446}"
S3_KEY="lambda-packages/${FUNCTION_NAME}.zip"
REGION="${AWS_REGION:-us-east-1}"

echo "=== Rebuilding Function Package (Code Only) ==="
echo "Function: $FUNCTION_NAME"
echo "Source: $FUNCTION_SRC"
echo "Build dir: $BUILD_DIR"
echo ""

# Check source exists
if [ ! -d "$FUNCTION_SRC" ]; then
    echo "ERROR: Source directory not found: $FUNCTION_SRC"
    exit 1
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
rm -f "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

# Copy source files
echo "Copying source files..."
cp -r "$FUNCTION_SRC"/* "$BUILD_DIR/"

# Create zip (exclude cache files)
echo "Creating zip file..."
cd "$BUILD_DIR"
zip -r "$ZIP_FILE" . -q -x "*.pyc" -x "__pycache__/*" -x "*.pyo" -x ".DS_Store"

ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "Package created: $ZIP_FILE"
echo "Size: $ZIP_SIZE"
echo ""

# Upload to S3
echo "Uploading to S3..."
aws s3 cp "$ZIP_FILE" "s3://${S3_BUCKET}/${S3_KEY}" --region "$REGION"

echo ""
echo "=== Package Rebuilt and Uploaded ==="
echo "S3 location: s3://${S3_BUCKET}/${S3_KEY}"
echo ""
echo "To update Lambda function:"
echo "aws lambda update-function-code \\"
echo "  --function-name fraudguard-ai-dev-GoogleAdsIngestion \\"
echo "  --s3-bucket $S3_BUCKET \\"
echo "  --s3-key $S3_KEY \\"
echo "  --region $REGION"
