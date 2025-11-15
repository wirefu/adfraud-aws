# Getting Started: Processing and Training Fraud Data

**Date**: November 2024  
**Status**: Step-by-Step Guide

---

## Current Status Check

✅ **Available**:
- Terraform-managed: DynamoDB table, S3 bucket
- CloudFormation-managed: Lambda functions, API Gateway
- TalkingData dataset: Available locally (`data/talkingdata/`)
- Training PRD: Complete with requirements

❌ **Missing**:
- SageMaker execution role
- Feature engineering script
- Processed training data in S3
- Training script
- SageMaker endpoint

---

## Step-by-Step Implementation Plan

### Phase 1: Deploy SageMaker Infrastructure (30 minutes)

#### Step 1.1: Add SageMaker Resources to Terraform

Since you're using Terraform for infrastructure, add SageMaker resources:

**Create `terraform/sagemaker.tf`**:

```hcl
# SageMaker Execution Role
resource "aws_iam_role" "sagemaker_execution" {
  name = "${var.stack_name}-sagemaker-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "sagemaker.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_role_policy" "sagemaker_s3_access" {
  name = "S3Access"
  role = aws_iam_role.sagemaker_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.data.arn,
        "${aws_s3_bucket.data.arn}/*"
      ]
    }]
  })
}

# Output SageMaker role ARN
output "sagemaker_execution_role_arn" {
  description = "SageMaker Execution Role ARN"
  value       = aws_iam_role.sagemaker_execution.arn
}
```

**Apply Terraform**:

```bash
cd terraform
terraform plan
terraform apply
```

**Get the role ARN**:

```bash
terraform output sagemaker_execution_role_arn
```

---

### Phase 2: Create Feature Engineering Script (1-2 hours)

#### Step 2.1: Create Feature Engineering Script

**Create `scripts/process_training_data.py`**:

This script will:
1. Load TalkingData CSV
2. Engineer features to match production feature extractor
3. Handle missing features (IP reputation, user agent, etc.)
4. Save processed data to S3

**Key Requirements**:
- Map TalkingData columns to production features
- Handle 20+ features from `src/orchestrator/feature_extractor.py`
- Support multi-platform features (Google Ads, Meta, LinkedIn)
- Generate train/val/test splits (70/15/15)
- Save as CSV for SageMaker

**See `docs/DATA_TRAINING_PRD.md` Section 3.3** for feature requirements.

---

### Phase 3: Process and Upload Training Data (1-2 hours)

#### Step 3.1: Process TalkingData Locally

```bash
# Install dependencies
pip install pandas numpy scikit-learn imbalanced-learn boto3

# Process training data
python scripts/process_training_data.py \
  --input data/talkingdata/train_sample.csv \
  --output s3://fraudguard-ai-data-971422717446/fraud-detection/training/ \
  --environment dev
```

**What this does**:
- Loads TalkingData CSV
- Engineers features
- Splits into train/val/test
- Uploads to S3

#### Step 3.2: Verify Data in S3

```bash
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/
# Should see: train.csv, val.csv, test.csv
```

---

### Phase 4: Create Training Script (2-3 hours)

#### Step 4.1: Create SageMaker Training Script

**Create `scripts/train_xgboost_sagemaker.py`**:

This script will:
1. Set up SageMaker training job
2. Use built-in XGBoost algorithm
3. Configure hyperparameters
4. Handle class imbalance (`scale_pos_weight`)
5. Train baseline model
6. Save model artifact to S3

**Key Configuration**:
- Algorithm: SageMaker XGBoost (built-in)
- Instance: `ml.m5.xlarge`
- Hyperparameters: See `docs/XGBOOST_TRAINING_GUIDE.md`
- Class imbalance: `scale_pos_weight = sqrt(num_nonfraud / num_fraud)`

#### Step 4.2: Run Baseline Training

```bash
python scripts/train_xgboost_sagemaker.py \
  --s3-bucket fraudguard-ai-data-971422717446 \
  --s3-prefix fraud-detection/training \
  --sagemaker-role-arn <ROLE_ARN_FROM_STEP_1> \
  --environment dev
```

**Expected Output**:
- Model artifact in S3: `s3://.../models/xgboost/model.tar.gz`
- Training metrics in CloudWatch
- Baseline performance metrics

---

### Phase 5: Hyperparameter Optimization (2-4 hours)

#### Step 5.1: Create HPO Script

**Create `scripts/hpo_xgboost_sagemaker.py`**:

This script will:
1. Define hyperparameter ranges
2. Create HPO tuning job
3. Run 10 training jobs in parallel
4. Select best model

**Hyperparameter Ranges** (from PRD):
- `max_depth`: [3, 5, 7, 10]
- `eta` (learning_rate): [0.01, 0.1, 0.2, 0.3]
- `min_child_weight`: [1, 3, 5]
- `subsample`: [0.6, 0.8, 1.0]
- `colsample_bytree`: [0.6, 0.8, 1.0]

#### Step 5.2: Run HPO

```bash
python scripts/hpo_xgboost_sagemaker.py \
  --s3-bucket fraudguard-ai-data-971422717446 \
  --s3-prefix fraud-detection/training \
  --sagemaker-role-arn <ROLE_ARN> \
  --max-jobs 10 \
  --parallel-jobs 2
```

**Expected Duration**: 2-4 hours (depending on data size)

---

### Phase 6: Deploy Model to Endpoint (30 minutes)

#### Step 6.1: Create Deployment Script

**Create `scripts/deploy_sagemaker_endpoint.py`**:

This script will:
1. Create SageMaker model
2. Create endpoint configuration
3. Deploy endpoint
4. Test endpoint with sample requests

#### Step 6.2: Deploy Endpoint

```bash
python scripts/deploy_sagemaker_endpoint.py \
  --model-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/models/xgboost/model.tar.gz \
  --sagemaker-role-arn <ROLE_ARN> \
  --endpoint-name fraudguard-ai-dev-xgboost-endpoint \
  --instance-type ml.t2.medium
```

**Expected Output**:
- SageMaker endpoint: `fraudguard-ai-dev-xgboost-endpoint`
- Endpoint URL for inference

---

### Phase 7: Update Orchestrator Lambda (15 minutes)

#### Step 7.1: Update Lambda Environment Variable

The orchestrator Lambda needs the endpoint name:

```bash
aws lambda update-function-configuration \
  --function-name fraudguard-ai-dev-orchestrator \
  --environment Variables="{SAGEMAKER_ENDPOINT=fraudguard-ai-dev-xgboost-endpoint}"
```

Or update in Terraform/CloudFormation template.

---

## Quick Start Checklist

### Immediate Actions (Today)

- [ ] **Step 1**: Deploy SageMaker execution role via Terraform
- [ ] **Step 2**: Create feature engineering script
- [ ] **Step 3**: Process TalkingData sample and upload to S3

### This Week

- [ ] **Step 4**: Create and run baseline training
- [ ] **Step 5**: Run HPO for optimized model
- [ ] **Step 6**: Deploy model to endpoint
- [ ] **Step 7**: Update orchestrator Lambda

### Next Week

- [ ] Set up retraining pipeline (weekly schedule)
- [ ] Monitor model performance
- [ ] Add more training data sources

---

## Required Scripts to Create

1. **`scripts/process_training_data.py`** - Feature engineering
2. **`scripts/train_xgboost_sagemaker.py`** - Baseline training
3. **`scripts/hpo_xgboost_sagemaker.py`** - Hyperparameter optimization
4. **`scripts/deploy_sagemaker_endpoint.py`** - Endpoint deployment

---

## Key Resources

- **S3 Bucket**: `fraudguard-ai-data-971422717446`
- **S3 Training Path**: `s3://fraudguard-ai-data-971422717446/fraud-detection/training/`
- **S3 Model Path**: `s3://fraudguard-ai-data-971422717446/fraud-detection/models/`
- **DynamoDB Table**: `fraudguard-events-dev`
- **SageMaker Role**: Will be created in Step 1

---

## Cost Estimates

- **Training** (baseline): ~$1-2 per run
- **HPO** (10 jobs): ~$10-20
- **Endpoint** (ml.t2.medium): ~$30-50/month
- **Total First Month**: ~$50-70

---

## Troubleshooting

### Issue: SageMaker role not found
**Solution**: Complete Step 1.1 and apply Terraform

### Issue: Training data not in S3
**Solution**: Complete Step 3.1 to process and upload data

### Issue: Feature mismatch
**Solution**: Ensure feature engineering matches `src/orchestrator/feature_extractor.py`

### Issue: Class imbalance
**Solution**: Use `scale_pos_weight` or SMOTE (see PRD Section 3.4)

---

## Next Steps After Training

1. **Evaluate Model**: Check metrics (F1, ROC AUC, Cohen's Kappa)
2. **Test Integration**: Verify orchestrator calls endpoint correctly
3. **Monitor Performance**: Set up CloudWatch alarms
4. **Retrain Pipeline**: Automate weekly retraining

---

## References

- **Training PRD**: `docs/DATA_TRAINING_PRD.md`
- **XGBoost Guide**: `docs/XGBOOST_TRAINING_GUIDE.md`
- **Feature Extractor**: `src/orchestrator/feature_extractor.py`
- **AWS Blog**: `docs/AWS_BLOG_LEARNINGS.md`

---

## Getting Help

If you encounter issues:
1. Check CloudWatch logs for training jobs
2. Review SageMaker training job status in AWS Console
3. Verify S3 bucket permissions
4. Check IAM role permissions
5. Review `docs/DATA_TRAINING_PRD.md` for detailed requirements

