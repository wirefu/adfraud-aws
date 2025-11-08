# Dashboard Deployment Guide

This guide explains how to deploy the Fraud Analytics Dashboard to AWS App Runner.

## Prerequisites

1. **AWS Account** with App Runner access
2. **Docker** installed (for local testing)
3. **AWS CLI** configured
4. **ECR Repository** created (for container deployment)

## Deployment Options

### Option 1: Deploy from ECR (Recommended)

1. **Build and push Docker image:**
   ```bash
   # Build image
   docker build -t fraudguard-dashboard:latest .
   
   # Tag for ECR
   docker tag fraudguard-dashboard:latest \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com/fraudguard-dashboard:latest
   
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     <account-id>.dkr.ecr.us-east-1.amazonaws.com
   
   # Push image
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/fraudguard-dashboard:latest
   ```

2. **Create App Runner service:**
   ```bash
   aws apprunner create-service \
     --service-name fraudguard-dashboard \
     --source-configuration '{
       "ImageRepository": {
         "ImageIdentifier": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/fraudguard-dashboard:latest",
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
     }' \
     --auto-scaling-configuration-arn <auto-scaling-config-arn>
   ```

### Option 2: Deploy from GitHub

1. **Push code to GitHub repository**

2. **Create App Runner service via Console:**
   - Go to AWS App Runner Console
   - Click "Create service"
   - Select "Source code repository"
   - Connect to GitHub
   - Select repository and branch
   - Configure build settings:
     - Build command: `pip install -r dashboard/requirements.txt`
     - Start command: `streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0`
   - Set environment variables
   - Deploy

### Option 3: Deploy from Local Source

1. **Create App Runner service with local source:**
   ```bash
   aws apprunner create-service \
     --service-name fraudguard-dashboard \
     --source-configuration '{
       "CodeRepository": {
         "RepositoryUrl": "https://github.com/your-org/fraudguard-aws",
         "SourceCodeVersion": {
           "Type": "BRANCH",
           "Value": "main"
         },
         "CodeConfiguration": {
           "ConfigurationSource": "API",
           "CodeConfigurationValues": {
             "BuildCommand": "pip install -r dashboard/requirements.txt",
             "Runtime": "PYTHON_3",
             "StartCommand": "streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0"
           }
         }
       }
     }' \
     --instance-configuration '{
       "Cpu": "1 vCPU",
       "Memory": "2 GB"
     }'
   ```

## Configuration

### Environment Variables

Set in App Runner service configuration:

- `DYNAMODB_TABLE_NAME`: DynamoDB table name (e.g., `fraudguard-events-dev`)
- `S3_BUCKET_NAME`: S3 bucket name (optional)
- `AWS_REGION`: AWS region (default: `us-east-1`)

### IAM Permissions

App Runner service role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/fraudguard-events-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::fraudguard-data-*/*"
    }
  ]
}
```

## Auto-Scaling

Configure auto-scaling in App Runner:

- **Min instances**: 1
- **Max instances**: 5
- **Concurrency**: 10 requests per instance
- **CPU utilization**: 70% target

## Monitoring

### CloudWatch Metrics

- `RequestCount`: Number of requests
- `ResponseTime`: Response latency
- `CPUUtilization`: CPU usage
- `MemoryUtilization`: Memory usage

### CloudWatch Logs

- Log group: `/aws/apprunner/fraudguard-dashboard/service/application`

## Troubleshooting

### Dashboard not loading
- Check App Runner service status
- Verify environment variables
- Review CloudWatch logs

### No data displayed
- Verify DynamoDB table name
- Check IAM permissions
- Verify events exist in DynamoDB

### Performance issues
- Increase instance size
- Enable auto-scaling
- Optimize DynamoDB queries

## Cost Estimation

### App Runner Pricing (us-east-1)

- **vCPU**: $0.064 per vCPU-hour
- **Memory**: $0.007 per GB-hour
- **Requests**: $0.000001 per request

### Estimated Monthly Cost

For 1 vCPU, 2 GB, 100k requests/month:
- vCPU: 1 × 730 hours × $0.064 = $46.72
- Memory: 2 × 730 hours × $0.007 = $10.22
- Requests: 100k × $0.000001 = $0.10
- **Total: ~$57/month**

## Next Steps

1. Set up custom domain (optional)
2. Configure authentication (optional)
3. Set up CloudWatch alarms
4. Configure auto-scaling
5. Set up CI/CD for deployments

