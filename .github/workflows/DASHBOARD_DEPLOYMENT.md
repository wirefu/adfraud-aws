# Dashboard Deployment Workflow

This document explains the GitHub Actions workflow for deploying the Fraud Analytics Dashboard to AWS ECS with Application Load Balancer (ALB).

## Overview

The dashboard deployment workflow (`dashboard-deploy.yml`) automatically builds, pushes, and deploys the Streamlit dashboard to AWS ECS (Fargate) behind an Application Load Balancer whenever dashboard code changes. The ECS infrastructure is managed via CloudFormation in `template.yaml`.

## Workflow Triggers

### Automatic Deployment

The workflow runs automatically when:
- Code is pushed to `main` or `develop` branches
- Changes are made to files in the `dashboard/` directory
- The workflow file itself is updated

### Manual Deployment

You can manually trigger the workflow:
1. Go to GitHub Actions tab
2. Select "Deploy Dashboard" workflow
3. Click "Run workflow"
4. Choose the environment (dev, staging, prod)
5. Click "Run workflow"

## Workflow Steps

### 1. Checkout Code
- Checks out the repository code

### 2. Configure AWS Credentials
- Configures AWS credentials from GitHub secrets
- Required secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### 3. Login to Amazon ECR
- Authenticates with Amazon ECR
- Retrieves ECR registry URL

### 4. Build Docker Image
- Builds Docker image from `dashboard/Dockerfile`
- Tags image with commit SHA and environment
- Creates both versioned and `latest` tags

### 5. Push Docker Image to ECR
- Pushes image to ECR repository
- Both versioned and `latest` tags are pushed

### 6. Get ECS Cluster and Service Info
- Retrieves ECS cluster, service, and task definition from CloudFormation stack
- Extracts resource names and ARNs

### 7. Register New ECS Task Definition
- Gets current task definition
- Updates with new Docker image URI
- Registers new task definition revision

### 8. Update ECS Service
- Updates ECS service with new task definition
- Forces new deployment to pick up updated image
- Service performs rolling update

### 9. Wait for Service to Stabilize
- Waits for ECS service to reach stable state
- Ensures new tasks are healthy before completing

### 10. Get ALB URL
- Retrieves Application Load Balancer DNS name from CloudFormation outputs
- Displays dashboard URL in workflow summary

## Configuration

### Environment Variables

The workflow uses these environment variables:

- `AWS_REGION`: AWS region (default: `us-east-1`)
- `ECR_REPOSITORY`: ECR repository name (default: `fraudguard-dashboard`)
- `STACK_NAME`: CloudFormation stack name (default: `fraudguard-ai`)

### Environment-Specific Configuration

Each environment has different DynamoDB table names:

- **dev**: `fraudguard-events-dev`
- **staging**: `fraudguard-events-staging`
- **prod**: `fraudguard-events-prod`

### Required GitHub Secrets

1. **AWS_ACCESS_KEY_ID**: AWS access key ID
2. **AWS_SECRET_ACCESS_KEY**: AWS secret access key

### Required AWS Resources

1. **ECR Repository**: Must exist before first deployment
   ```bash
   aws ecr create-repository --repository-name fraudguard-dashboard --region us-east-1
   ```

2. **CloudFormation Stack**: Must be deployed with dashboard resources
   - ECS Cluster (`DashboardCluster`)
   - ECS Service (`DashboardService`)
   - Application Load Balancer (`DashboardALB`)
   - Task Definition (`DashboardTaskDefinition`)
   - IAM Roles and Security Groups

3. **IAM Permissions**: The AWS credentials need:
   - `ecr:*` permissions for the ECR repository
   - `ecs:*` permissions for ECS service updates
   - `cloudformation:DescribeStacks` to read stack outputs
   - `elasticloadbalancing:DescribeTargetGroups` for health checks

## Setup Instructions

### 1. Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name fraudguard-dashboard \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256
```

### 2. Deploy CloudFormation Stack

Deploy the main CloudFormation stack that includes dashboard resources:

```bash
sam deploy --stack-name fraudguard-ai --parameter-overrides Environment=dev
```

This creates:
- ECS Cluster and Service
- Application Load Balancer
- Task Definition
- IAM Roles
- Security Groups
- CloudWatch Log Groups

### 3. Configure GitHub Secrets

Go to GitHub repository → Settings → Secrets and variables → Actions:

1. Add `AWS_ACCESS_KEY_ID`
2. Add `AWS_SECRET_ACCESS_KEY`

### 4. Create IAM User/Role

Create an IAM user or role with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition",
        "ecs:UpdateService"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackResources"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5. Test Deployment

1. Make a change to `dashboard/app.py`
2. Commit and push to `main` or `develop`
3. Check GitHub Actions tab for workflow execution
4. Verify deployment in AWS ECS console
5. Access dashboard at ALB URL from CloudFormation outputs

## Troubleshooting

### Workflow Fails: ECR Repository Not Found

**Error:** `RepositoryNotFoundException`

**Solution:**
```bash
aws ecr create-repository --repository-name fraudguard-dashboard --region us-east-1
```

### Workflow Fails: Access Denied

**Error:** `AccessDeniedException`

**Solution:**
- Verify AWS credentials in GitHub secrets
- Check IAM permissions include ECR and ECS access
- Ensure IAM user has `iam:PassRole` permission

### Workflow Fails: ECS Service Not Found

**Error:** `ServiceNotFoundException` or task definition not found

**Solution:**
- Ensure CloudFormation stack is deployed with dashboard resources
- Verify stack name matches `STACK_NAME` in workflow (default: `fraudguard-ai`)
- Check that ECS cluster and service exist in the stack

### Deployment Takes Too Long

**Solution:**
- ECS deployments typically take 2-5 minutes
- The workflow waits for service to stabilize
- Check ECS console for task status
- Verify ALB target health is healthy

### Service URL Not Retrieved

**Solution:**
- Verify CloudFormation stack has `DashboardALBDNS` output
- Check ALB is in active state
- Ensure ECS tasks are running and healthy

## Monitoring

### GitHub Actions

- View workflow runs in GitHub Actions tab
- Check workflow logs for detailed output
- Review deployment summary in workflow run

### AWS ECS Console

- Monitor service status and running tasks
- View task definition revisions
- Check service events and deployments
- View task logs

### AWS Application Load Balancer

- Monitor target health
- View request metrics
- Check access logs

### CloudWatch

- ECS service logs: `/ecs/fraudguard-ai-dashboard`
- Service metrics: CPU, memory, request count, latency
- ALB metrics: request count, response time, error rates

## Best Practices

1. **Test Locally First**: Test dashboard changes locally before pushing
2. **Use Feature Branches**: Test on feature branches before merging to main
3. **Monitor Deployments**: Check deployment status after each push
4. **Review Logs**: Check ECS task logs and ALB access logs if dashboard doesn't work
5. **Environment Separation**: Use different environments for dev/staging/prod

## Next Steps

1. ✅ Set up ECR repository
2. ✅ Configure GitHub secrets
3. ✅ Test deployment workflow
4. ✅ Monitor first deployment
5. ✅ Verify dashboard accessibility

