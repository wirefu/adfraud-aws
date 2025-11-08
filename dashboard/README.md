# Fraud Analytics Dashboard

A Streamlit-based web dashboard for monitoring real-time fraud metrics, campaign analysis, and event details.

## Features

### 1. Real-Time Overview
- Total events (last hour/day/week)
- Fraud rate percentage
- Top fraud signals
- Geographic heatmap of fraud
- Fraud type distribution

### 2. Campaign Analysis
- Fraud rate by campaign
- Click pattern visualizations
- Hourly click patterns
- Campaign summary tables

### 3. Event Detail View
- Individual event inspection
- Fraud analysis details
- Fraud signals
- AI-generated explanations

## Local Development

### Prerequisites
- Python 3.11+
- AWS credentials configured (for DynamoDB access)
- Streamlit installed

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export DYNAMODB_TABLE_NAME=fraudguard-events-dev
   export S3_BUCKET_NAME=your-bucket-name
   export AWS_REGION=us-east-1
   ```

3. **Run dashboard:**
   ```bash
   streamlit run app.py
   ```

4. **Access dashboard:**
   Open http://localhost:8501 in your browser

## AWS App Runner Deployment

### Prerequisites
- AWS CLI configured
- Docker installed (for local testing)
- App Runner service created

### Deployment Steps

1. **Build Docker image (optional, for local testing):**
   ```bash
   docker build -t fraudguard-dashboard .
   docker run -p 8501:8501 fraudguard-dashboard
   ```

2. **Deploy to App Runner:**
   ```bash
   # Using AWS CLI
   aws apprunner create-service \
     --service-name fraudguard-dashboard \
     --source-configuration '{
       "ImageRepository": {
         "ImageIdentifier": "your-ecr-repo/fraudguard-dashboard:latest",
         "ImageRepositoryType": "ECR",
         "ImageConfiguration": {
           "Port": "8501",
           "RuntimeEnvironmentVariables": {
             "DYNAMODB_TABLE_NAME": "fraudguard-events-dev",
             "AWS_REGION": "us-east-1"
           }
         }
       }
     }' \
     --instance-configuration '{
       "Cpu": "1 vCPU",
       "Memory": "2 GB"
     }'
   ```

3. **Or use App Runner console:**
   - Go to AWS App Runner Console
   - Create new service
   - Connect to source (ECR, GitHub, etc.)
   - Configure environment variables
   - Deploy

## Configuration

### Environment Variables

- `DYNAMODB_TABLE_NAME`: DynamoDB table name for events
- `S3_BUCKET_NAME`: S3 bucket name (optional)
- `AWS_REGION`: AWS region (default: us-east-1)

### IAM Permissions

The App Runner service role needs:
- `dynamodb:Scan` on events table
- `dynamodb:Query` on events table
- `dynamodb:GetItem` on events table
- `dynamodb:DescribeTable` on events table
- `s3:GetObject` on data bucket (optional)

## Features

### Real-Time Data
- Automatically refreshes data from DynamoDB
- Configurable time ranges (1h, 24h, 7d)
- Caching for performance

### Visualizations
- Interactive charts using Plotly
- Geographic heatmaps
- Time series analysis
- Fraud type distribution

### AI Explanations
- Natural language fraud explanations
- Fraud signal breakdown
- Evidence-based reasoning

## Troubleshooting

### Dashboard not loading
- Check AWS credentials are configured
- Verify DynamoDB table name is correct
- Check IAM permissions

### No data displayed
- Verify events exist in DynamoDB
- Check time range selection
- Review CloudWatch logs

### Performance issues
- Enable caching (already implemented)
- Reduce time range
- Optimize DynamoDB queries

## Next Steps

1. Add authentication (optional)
2. Add export functionality
3. Add alerting/notifications
4. Add custom date range selector
5. Add more visualization types

