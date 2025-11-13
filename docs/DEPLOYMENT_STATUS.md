# Deployment Status

## Current Status

### ❌ Not Deployed
The AWS infrastructure has **not been deployed yet**. The DynamoDB table and other resources do not exist in AWS.

## Why the Table is Not Found

1. **Stack Not Deployed**: The CloudFormation stack (`fraudguard-ai`) has not been deployed to AWS
2. **Table Doesn't Exist**: Since the stack isn't deployed, the DynamoDB table doesn't exist

## How to Deploy

### Option 1: Deploy Full Stack (Recommended)

Deploy the entire infrastructure including DynamoDB, S3, Lambda functions, and API Gateway:

```bash
# Build the SAM application
sam build

# Deploy to AWS
sam deploy --guided
```

This will:
- Create the DynamoDB table: `fraudguard-events-dev`
- Create the S3 bucket for data storage
- Deploy all Lambda functions
- Create API Gateway
- Set up IAM roles and permissions

### Option 2: Deploy Just the Table (Quick Test)

If you only need the table for dashboard testing:

```bash
# Create table manually
aws dynamodb create-table \
  --table-name fraudguard-events-dev \
  --attribute-definitions \
    AttributeName=event_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
    AttributeName=campaign_id,AttributeType=S \
    AttributeName=device_id,AttributeType=S \
  --key-schema \
    AttributeName=event_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    'IndexName=campaign-timestamp-index,KeySchema=[{AttributeName=campaign_id,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
    'IndexName=device-timestamp-index,KeySchema=[{AttributeName=device_id,KeyType=HASH},{AttributeName=timestamp,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
  --region us-east-1
```

## Table Name Configuration

### Template Definition
- **Table Name**: `fraudguard-events-${Environment}`
- **Default Environment**: `dev`
- **Actual Table Name**: `fraudguard-events-dev`

### Dashboard Configuration
- **Default Table Name**: `fraudguard-events-dev` (matches template)
- **Can be overridden**: Set `DYNAMODB_TABLE_NAME` environment variable

## After Deployment

Once deployed, the dashboard will:
1. ✅ Connect to the DynamoDB table
2. ✅ Fetch real events from the table
3. ✅ Display actual fraud detection data

Until then, the dashboard will:
- ⚠️ Show a warning that the table doesn't exist
- ✅ Automatically use mock data for demonstration
- ✅ Continue to function normally

## Verify Deployment

After deploying, verify the table exists:

```bash
# List tables
aws dynamodb list-tables --region us-east-1

# Describe the table
aws dynamodb describe-table \
  --table-name fraudguard-events-dev \
  --region us-east-1
```

## Next Steps

1. **Deploy the stack**: Run `sam deploy --guided`
2. **Verify table creation**: Check AWS Console or use AWS CLI
3. **Test dashboard**: The dashboard should now connect to the real table
4. **Send test events**: Use the API to send events and see them in the dashboard

