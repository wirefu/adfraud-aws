# Option B: AWS-Native Processing - Quick Start

**Approach**: SageMaker Processing Jobs  
**Status**: Ready to Use

---

## Quick Start (3 Steps)

### Step 1: Upload Raw Data to S3

```bash
# Upload TalkingData to S3
aws s3 cp data/talkingdata/train.csv \
    s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/train.csv

# Verify
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/
```

### Step 2: Launch Processing Job

```bash
# Simple (auto-detects from stack)
python scripts/launch_sagemaker_processing_job.py --stack-name fraudguard-ai-dev

# With options
python scripts/launch_sagemaker_processing_job.py \
    --stack-name fraudguard-ai-dev \
    --use-smote \
    --compress \
    --instance-type ml.m5.2xlarge
```

### Step 3: Verify and Train

```bash
# Check processed data
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/

# Run training
python scripts/train_xgboost_sagemaker.py --stack-name fraudguard-ai-dev
```

---

## What Gets Created

**S3 Structure**:
```
s3://bucket/fraud-detection/training/
├── raw/
│   └── train.csv              # Your raw data (upload manually)
└── processed/                 # Created by Processing Job
    ├── train.csv              # Processed training data
    ├── val.csv                # Processed validation data
    ├── test.csv               # Processed test data
    └── metrics.json           # Class imbalance metrics
```

**Processing Job**:
- Runs in AWS SageMaker
- Processes data using SKLearn processor
- Auto-scales based on data size
- Saves results to S3

---

## Cost Estimate

- **Processing**: ~$0.23-0.92/hour (depending on instance)
- **Duration**: 15-60 minutes (depending on data size)
- **Total**: ~$0.10-0.50 per processing run

---

## Full Documentation

See `docs/SAGEMAKER_PROCESSING_WORKFLOW.md` for complete details.

