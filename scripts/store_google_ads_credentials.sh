#!/bin/bash
# Store Google Ads API credentials in AWS Secrets Manager
# This script securely stores your credentials in AWS for production use

set -e

echo "=========================================="
echo "Google Ads API Credentials Storage"
echo "=========================================="
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed."
    echo "   Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials are not configured."
    echo "   Run: aws configure"
    exit 1
fi

echo "✅ AWS CLI is configured"
echo ""

# Get region
REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="fraudguard/google-ads-api-credentials"

echo "Region: ${REGION}"
echo "Secret Name: ${SECRET_NAME}"
echo ""

# Check if credentials file exists
CREDENTIALS_FILE="google-ads.yaml"
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "⚠️  Credentials file '$CREDENTIALS_FILE' not found."
    echo ""
    echo "Please create it first:"
    echo "  1. Copy google-ads.yaml.example to google-ads.yaml"
    echo "  2. Fill in your credentials"
    echo "  3. Run this script again"
    exit 1
fi

echo "✅ Found credentials file: $CREDENTIALS_FILE"
echo ""

# Check if secret already exists
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" &> /dev/null; then
    echo "⚠️  Secret '$SECRET_NAME' already exists."
    read -p "Do you want to update it? [y/N]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    
    # Update existing secret
    echo "Updating secret..."
    aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --secret-string file://"$CREDENTIALS_FILE" \
        --region "$REGION" \
        --description "Google Ads API credentials for FraudGuard" \
        > /dev/null
    
    echo "✅ Secret updated successfully!"
else
    # Create new secret
    echo "Creating new secret..."
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --description "Google Ads API credentials for FraudGuard" \
        --secret-string file://"$CREDENTIALS_FILE" \
        --region "$REGION" \
        > /dev/null
    
    echo "✅ Secret created successfully!"
fi

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. The credentials are now stored securely in AWS Secrets Manager"
echo "2. Your code will automatically retrieve them (no code changes needed)"
echo "3. Ensure your IAM role/user has permission to read the secret:"
echo ""
echo "   Required IAM permission:"
echo "   secretsmanager:GetSecretValue"
echo "   secretsmanager:DescribeSecret"
echo ""
echo "   Resource ARN:"
echo "   arn:aws:secretsmanager:${REGION}:*:secret:${SECRET_NAME}-*"
echo ""
echo "4. (Optional) Delete local credentials file for extra security:"
echo "   rm $CREDENTIALS_FILE"
echo ""
echo "✅ Done!"

