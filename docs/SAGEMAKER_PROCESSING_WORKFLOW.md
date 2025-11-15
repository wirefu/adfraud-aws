# SageMaker Processing Workflow (Option B)

**Date**: November 2024  
**Status**: Production-Ready  
**Approach**: AWS-Native Processing

---

## Overview

This document describes the **Option B: AWS-Native Processing** workflow for training data preparation. This approach processes data entirely in AWS using SageMaker Processing Jobs, providing:

- ✅ **Fully managed processing** - No local machine resources needed
- ✅ **Auto-scaling** - Handles large datasets efficiently
- ✅ **Production-ready** - Suitable for automated retraining pipelines
- ✅ **Cost-effective** - Pay only for processing time
- ✅ **Reproducible** - Same environment every time

---

## Architecture

```
┌─────────────────┐
│  Raw Data (S3)  │
│  train.csv      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  SageMaker Processing Job       │
│  - Loads data from S3           │
│  - Engineers features           │
│  - Preprocesses data            │
│  - Splits train/val/test        │
│  - Formats for SageMaker        │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Processed Data  │
│  (S3)           │
│  - train.csv    │
│  - val.csv      │
│  - test.csv     │
│  - metrics.json │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Training Jobs  │
│  (SageMaker)    │
└─────────────────┘
```

---

## Prerequisites

1. **Raw data uploaded to S3**:
   ```bash
   aws s3 cp data/talkingdata/train.csv \
       s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/train.csv
   ```

2. **SageMaker execution role** (already created via Terraform)

3. **S3 bucket** (already exists: `fraudguard-ai-data-971422717446`)

---

## Step-by-Step Workflow

### Step 1: Upload Raw Data to S3

Upload your raw training data to S3:

```bash
# Upload TalkingData
aws s3 cp data/talkingdata/train.csv \
    s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/train.csv

# Verify upload
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/
```

**S3 Structure**:
```
s3://bucket/fraud-detection/training/
├── raw/
│   └── train.csv          # Raw TalkingData
└── processed/             # Will be created by Processing Job
    ├── train.csv          # Processed training data
    ├── val.csv            # Processed validation data
    ├── test.csv           # Processed test data
    └── metrics.json       # Class imbalance metrics
```

### Step 2: Launch SageMaker Processing Job

Use the launch script to create and run the processing job:

```bash
# Basic usage (auto-detects from stack)
python scripts/launch_sagemaker_processing_job.py \
    --stack-name fraudguard-ai-dev

# With explicit parameters
python scripts/launch_sagemaker_processing_job.py \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --input-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/ \
    --output-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/ \
    --sagemaker-role-arn arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role \
    --instance-type ml.m5.xlarge

# With SMOTE and compression
python scripts/launch_sagemaker_processing_job.py \
    --stack-name fraudguard-ai-dev \
    --use-smote \
    --compress \
    --instance-type ml.m5.2xlarge

# Test with limited rows
python scripts/launch_sagemaker_processing_job.py \
    --stack-name fraudguard-ai-dev \
    --nrows 10000 \
    --instance-type ml.m5.xlarge
```

**What happens**:
1. Script packages training modules (`training/`, `scripts/`) into tar.gz
2. Uploads code package to S3
3. Creates SageMaker Processing Job with SKLearn processor
4. Job runs in AWS, processes data, writes to S3
5. Returns processed data location

### Step 3: Monitor Processing Job

**AWS Console**:
```
https://console.aws.amazon.com/sagemaker/home#/processing-jobs/{job-name}
```

**AWS CLI**:
```bash
# Check status
aws sagemaker describe-processing-job \
    --processing-job-name fraudguard-data-processing-20241114-123456

# View logs
aws logs tail /aws/sagemaker/ProcessingJobs/fraudguard-data-processing-20241114-123456 --follow
```

**Expected Duration**:
- Small dataset (10k rows): ~5-10 minutes
- Medium dataset (100k rows): ~15-30 minutes
- Large dataset (1M+ rows): ~30-60 minutes

### Step 4: Verify Processed Data

After job completes, verify processed data in S3:

```bash
# List processed files
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/

# Download and inspect metrics
aws s3 cp s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/metrics.json - | jq
```

**Expected Output**:
- `train.csv` (or `train.csv.gz` if compressed)
- `val.csv` (or `val.csv.gz`)
- `test.csv` (or `test.csv.gz`)
- `metrics.json`

### Step 5: Run Training Jobs

Once processed data is ready, run training:

```bash
# Baseline training
python scripts/train_xgboost_sagemaker.py \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --s3-prefix fraud-detection/training/processed/ \
    --sagemaker-role-arn arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role

# Hyperparameter optimization
python scripts/hpo_xgboost_sagemaker.py \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --s3-prefix fraud-detection/training/processed/ \
    --sagemaker-role-arn arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role
```

---

## Scripts Overview

### 1. `scripts/process_training_data_sagemaker.py`

**Purpose**: Entry point script that runs inside SageMaker Processing Job

**Location**: Runs in `/opt/ml/processing/` inside the Processing Job container

**Responsibilities**:
- Loads raw data from S3 input
- Engineers features using `training/feature_engineering.py`
- Preprocesses data using `training/preprocessing.py`
- Splits data using `training/data_splitting.py`
- Formats for SageMaker XGBoost
- Saves processed data to S3 output

**Key Features**:
- Handles large datasets with chunking
- Supports SMOTE oversampling
- Optional gzip compression
- Calculates class imbalance metrics

### 2. `scripts/launch_sagemaker_processing_job.py`

**Purpose**: Launches SageMaker Processing Job from local machine

**Responsibilities**:
- Packages training modules into tar.gz
- Uploads code package to S3
- Creates SageMaker Processing Job
- Configures inputs/outputs
- Monitors job execution

**Key Features**:
- Auto-detects resources from CloudFormation stack
- Supports multiple instance types
- Configurable processing options
- Async execution support

---

## Configuration Options

### Instance Types

**Recommended**:
- `ml.m5.xlarge` - For datasets < 1M rows (4 vCPU, 16 GB RAM)
- `ml.m5.2xlarge` - For datasets 1M-10M rows (8 vCPU, 32 GB RAM)
- `ml.m5.4xlarge` - For datasets > 10M rows (16 vCPU, 64 GB RAM)

**Cost Estimates**:
- `ml.m5.xlarge`: ~$0.23/hour
- `ml.m5.2xlarge`: ~$0.46/hour
- `ml.m5.4xlarge`: ~$0.92/hour

### Processing Options

| Option | Description | Default |
|--------|-------------|---------|
| `--use-smote` | Apply SMOTE oversampling | False |
| `--compress` | Compress output files with gzip | False |
| `--nrows` | Limit rows for testing | None (all rows) |
| `--instance-type` | Processing instance type | `ml.m5.xlarge` |
| `--instance-count` | Number of instances | 1 |

---

## Comparison: Option A vs Option B

| Aspect | Option A (Local) | Option B (SageMaker Processing) |
|--------|------------------|-------------------------------|
| **Processing Location** | Local machine | AWS SageMaker |
| **Resource Requirements** | Local RAM/CPU | AWS managed |
| **Scalability** | Limited by local machine | Auto-scaling |
| **Cost** | Free (uses local resources) | Pay per hour (~$0.23-0.92/hr) |
| **Setup Complexity** | Low | Medium |
| **Best For** | Development, testing | Production, large datasets |
| **Reproducibility** | Depends on local env | Consistent AWS environment |

---

## Troubleshooting

### Issue: Processing Job Fails

**Check CloudWatch Logs**:
```bash
aws logs tail /aws/sagemaker/ProcessingJobs/{job-name} --follow
```

**Common Causes**:
- Missing dependencies in requirements.txt
- S3 permissions issue
- Out of memory (use larger instance)
- Data format issues

### Issue: Code Package Too Large

**Solution**: The launch script automatically packages only necessary files. If issues occur:
- Check that training modules are included
- Verify tar.gz size (< 250 MB recommended)

### Issue: Processing Takes Too Long

**Solutions**:
- Use larger instance type (`ml.m5.2xlarge` or `ml.m5.4xlarge`)
- Use `--nrows` to test with smaller dataset first
- Enable compression to reduce I/O time

### Issue: Missing Raw Data in S3

**Solution**: Ensure raw data is uploaded before launching:
```bash
aws s3 ls s3://bucket/fraud-detection/training/raw/
```

---

## Next Steps

After processing completes:

1. **Verify processed data**:
   ```bash
   aws s3 ls s3://bucket/fraud-detection/training/processed/
   ```

2. **Run baseline training**:
   ```bash
   python scripts/train_xgboost_sagemaker.py --stack-name fraudguard-ai-dev
   ```

3. **Run HPO** (optional):
   ```bash
   python scripts/hpo_xgboost_sagemaker.py --stack-name fraudguard-ai-dev
   ```

4. **Evaluate model**:
   ```bash
   python scripts/evaluate_model.py \
       --training-job-name {job-name} \
       --s3-bucket {bucket}
   ```

---

## References

- [SageMaker Processing Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/processing-job.html)
- [SKLearn Processor](https://docs.aws.amazon.com/sagemaker/latest/dg/processing-container.html)
- [Training Data PRD](./DATA_TRAINING_PRD.md)

