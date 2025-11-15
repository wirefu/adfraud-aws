# Terraform Deployment Guide

**Version**: 1.0  
**Date**: November 2024  
**Status**: Implementation Guide

---

## Overview

This guide explains how to deploy the FraudGuard AI infrastructure using **HashiCorp Terraform** instead of AWS SAM/CloudFormation. Terraform provides better state management, modularity, and team collaboration features.

## Why Terraform?

### Advantages over SAM/CloudFormation

1. **Better State Management**
   - Remote state with S3 backend
   - State locking with DynamoDB
   - State versioning and rollback

2. **Modular Architecture**
   - Reusable modules
   - Environment-specific configurations
   - Better code organization

3. **Team Collaboration**
   - Workspaces for multiple environments
   - Better conflict resolution
   - Plan/Apply workflow

4. **Provider Ecosystem**
   - Support for multiple cloud providers
   - Rich provider ecosystem
   - Better tooling integration

5. **Infrastructure as Code Best Practices**
   - Version control friendly
   - Better testing capabilities
   - More flexible configuration

## Current Status

The project currently uses:
- **AWS SAM** with CloudFormation (`template.yaml`)
- **GitHub Actions** for CI/CD (`.github/workflows/cd.yml`)

## Migration Strategy

### Option 1: Full Migration (Recommended)

Replace SAM/CloudFormation entirely with Terraform:

1. **Create Terraform configurations** for all resources
2. **Import existing resources** (if any)
3. **Update CI/CD** to use Terraform
4. **Remove SAM/CloudFormation** files

### Option 2: Hybrid Approach

Use Terraform for new resources, keep SAM for existing:

1. **Use Terraform** for SageMaker resources
2. **Keep SAM** for Lambda/API Gateway
3. **Gradually migrate** resources over time

### Option 3: Parallel Deployment

Run both systems in parallel:

1. **Deploy with Terraform** to new environment
2. **Compare outputs** with SAM deployment
3. **Switch over** when confident

## Terraform Structure

```
terraform/
├── main.tf                 # Main configuration, providers
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── dynamodb.tf             # DynamoDB table and indexes
├── s3.tf                   # S3 bucket and policies
├── lambda.tf               # Lambda functions
├── api_gateway.tf           # API Gateway configuration
├── sagemaker.tf            # SageMaker resources
├── vpc.tf                  # VPC, subnets, security groups
├── iam.tf                  # IAM roles and policies
├── alb.tf                  # Application Load Balancer
├── modules/                # Reusable modules
│   ├── lambda/            # Lambda module
│   ├── sagemaker/         # SageMaker module
│   └── vpc/               # VPC module
├── environments/           # Environment configs
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
└── README.md
```

## Key Resources to Migrate

### 1. DynamoDB Table
- Table: `fraudguard-events-{environment}`
- Global Secondary Indexes (5)
- TTL enabled
- Point-in-time recovery

### 2. S3 Bucket
- Bucket: `{stack-name}-data-{account-id}`
- Versioning enabled
- Lifecycle policies
- Encryption

### 3. Lambda Functions
- Ingestion Handler
- Fraud Orchestrator
- AI Analyzer
- Decision Combiner
- Google Ads Tracking
- Data Processing (for training)

### 4. API Gateway
- HTTP API
- CORS configuration
- Lambda integrations

### 5. SageMaker Resources
- Execution Role
- Endpoint (after training)
- Endpoint Config
- Model

### 6. VPC/Networking
- VPC
- Subnets
- Internet Gateway
- Security Groups
- Application Load Balancer

## Implementation Steps

### Step 1: Setup Terraform Backend

1. **Create S3 bucket for state**:
```bash
aws s3 mb s3://fraudguard-ai-terraform-state --region us-east-1
aws s3api put-bucket-versioning \
  --bucket fraudguard-ai-terraform-state \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket fraudguard-ai-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

2. **Create DynamoDB table for locking**:
```bash
aws dynamodb create-table \
  --table-name fraudguard-ai-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

3. **Configure backend in `main.tf`**:
```hcl
terraform {
  backend "s3" {
    bucket         = "fraudguard-ai-terraform-state"
    key            = "fraudguard-ai/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "fraudguard-ai-terraform-locks"
  }
}
```

### Step 2: Create Terraform Configurations

See the `terraform/` directory for complete configurations. Key files:

- **`dynamodb.tf`**: DynamoDB table with all indexes
- **`s3.tf`**: S3 bucket with policies
- **`lambda.tf`**: All Lambda functions
- **`api_gateway.tf`**: API Gateway setup
- **`sagemaker.tf`**: SageMaker resources
- **`vpc.tf`**: VPC and networking

### Step 3: Initialize and Plan

```bash
cd terraform
terraform init
terraform plan -out=tfplan
```

### Step 4: Apply Configuration

```bash
terraform apply tfplan
```

### Step 5: Import Existing Resources (if any)

If you have existing resources deployed via SAM:

```bash
# Import DynamoDB table
terraform import aws_dynamodb_table.events_table fraudguard-events-dev

# Import S3 bucket
terraform import aws_s3_bucket.data_bucket fraudguard-ai-data-{account-id}

# Import Lambda functions
terraform import aws_lambda_function.ingestion_handler fraudguard-ai-dev-ingestion-handler
terraform import aws_lambda_function.orchestrator fraudguard-ai-dev-orchestrator
# ... etc
```

## CI/CD Integration

### Update GitHub Actions Workflow

Replace `.github/workflows/cd.yml`:

```yaml
name: CD

on:
  push:
    branches: [ main ]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        default: 'dev'
        type: choice
        options:
          - dev
          - staging
          - prod

env:
  AWS_REGION: us-east-1
  TF_VERSION: 1.5.0

jobs:
  deploy:
    name: Deploy to AWS with Terraform
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: ${{ env.TF_VERSION }}
          terraform_wrapper: false
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Terraform Init
        working-directory: terraform
        run: |
          terraform init \
            -backend-config="bucket=fraudguard-ai-terraform-state" \
            -backend-config="key=fraudguard-ai/${{ github.event.inputs.environment || 'dev' }}/terraform.tfstate" \
            -backend-config="region=${{ env.AWS_REGION }}" \
            -backend-config="dynamodb_table=fraudguard-ai-terraform-locks"
      
      - name: Terraform Validate
        working-directory: terraform
        run: terraform validate
      
      - name: Terraform Plan
        working-directory: terraform
        run: |
          terraform plan \
            -var="environment=${{ github.event.inputs.environment || 'dev' }}" \
            -out=tfplan
      
      - name: Terraform Apply
        working-directory: terraform
        run: terraform apply -auto-approve tfplan
      
      - name: Get Outputs
        working-directory: terraform
        run: |
          echo "API_URL=$(terraform output -raw api_gateway_url)" >> $GITHUB_OUTPUT
          echo "DynamoDB Table: $(terraform output -raw dynamodb_table_name)"
          echo "S3 Bucket: $(terraform output -raw s3_bucket_name)"
```

## Environment-Specific Configurations

### Development

```bash
cd terraform
terraform workspace select dev
terraform plan -var="environment=dev"
terraform apply -var="environment=dev"
```

### Staging/Production

```bash
cd terraform/environments/staging
terraform init
terraform plan -var-file=staging.tfvars
terraform apply -var-file=staging.tfvars
```

## Variables

Key variables (see `variables.tf`):

- `environment`: Environment name (dev, staging, prod)
- `aws_region`: AWS region (default: us-east-1)
- `enable_sagemaker`: Enable SageMaker resources
- `enable_vpc`: Enable VPC resources
- `lambda_timeout`: Lambda timeout (default: 30)
- `lambda_memory_size`: Lambda memory (default: 512)

## Outputs

Key outputs (see `outputs.tf`):

- `dynamodb_table_name`: DynamoDB table name
- `s3_bucket_name`: S3 bucket name
- `api_gateway_url`: API Gateway endpoint URL
- `lambda_functions`: Lambda function names and ARNs
- `sagemaker_endpoint_name`: SageMaker endpoint (if enabled)

## Best Practices

1. **Always run `terraform plan` before `apply`**
2. **Use remote state** for team collaboration
3. **Version control** all `.tf` files (never commit `.tfstate`)
4. **Use modules** for reusable components
5. **Tag resources** consistently
6. **Use workspaces** or separate directories for environments
7. **Review changes** carefully before applying
8. **Use `terraform fmt`** to format code
9. **Use `terraform validate`** to check syntax
10. **Document** all variables and outputs

## Troubleshooting

### State Lock Issues

```bash
# Check for locks
aws dynamodb scan --table-name fraudguard-ai-terraform-locks

# Force unlock (use with caution)
terraform force-unlock <LOCK_ID>
```

### Import Errors

```bash
# Verify resource exists
aws dynamodb describe-table --table-name fraudguard-events-dev

# Check resource IDs match
terraform show
```

### Provider Issues

```bash
# Update providers
terraform init -upgrade

# Check provider versions
terraform version
```

## Migration Checklist

- [ ] Create S3 bucket for Terraform state
- [ ] Create DynamoDB table for state locking
- [ ] Configure Terraform backend
- [ ] Create all Terraform resource files
- [ ] Test `terraform init`
- [ ] Test `terraform plan`
- [ ] Import existing resources (if any)
- [ ] Update CI/CD workflows
- [ ] Test deployment in dev environment
- [ ] Document migration process
- [ ] Train team on Terraform
- [ ] Deploy to staging
- [ ] Deploy to production
- [ ] Remove SAM/CloudFormation files (after verification)

## Resources

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices/index.html)
- [Terraform State Management](https://www.terraform.io/docs/state/index.html)
- [Terraform Workspaces](https://www.terraform.io/docs/state/workspaces.html)

## Next Steps

1. Review existing Terraform files in `terraform/` directory
2. Complete missing resource configurations
3. Set up remote state backend
4. Test deployment in dev environment
5. Update CI/CD workflows
6. Migrate existing resources (if any)

