# Bot Traffic Detection: XGBoost Training in SageMaker

Complete step-by-step guide to train an XGBoost model in SageMaker specifically optimized for bot traffic detection.

## Overview

This guide walks you through training an XGBoost model that focuses on detecting bot traffic using the 8 key bot detection features identified in your feature set.

### Bot Traffic Detection Features

The model will use these **8 primary features** for bot detection:
1. `ua_is_bot` - Bot signatures in user agent
2. `ua_entropy` - User agent complexity
3. `ip_click_count_24h` - Click velocity from IP
4. `device_click_count_1h` - Rapid clicks from device
5. `time_since_last_click` - Short intervals between clicks
6. `click_to_view_time_ms` - Zero or very short view times
7. `referrer_is_valid` - Missing/invalid referrers
8. `engagement_score` - Low engagement patterns

**Note**: The model will still use all 29 features, but we'll optimize hyperparameters and focus evaluation on bot traffic detection.

---

## Prerequisites

### 1. AWS Setup

**Check AWS credentials:**
```bash
aws sts get-caller-identity
```

**Verify SageMaker access:**
```bash
aws sagemaker list-training-jobs --max-results 1
```

### 2. Required Resources

- **S3 Bucket**: For training data and model artifacts
- **SageMaker Execution Role**: IAM role with SageMaker permissions
- **Training Data**: Processed data with features (at least 100k samples)

### 3. Get SageMaker Role ARN

**Option A: From Terraform (if deployed)**
```bash
terraform output sagemaker_execution_role_arn
```

**Option B: Find existing role**
```bash
aws iam list-roles --query 'Roles[?contains(RoleName, `sagemaker`)].Arn' --output text
```

**Expected format**: `arn:aws:iam::ACCOUNT_ID:role/fraudguard-ai-sagemaker-execution-role`

### 4. Verify S3 Bucket

```bash
# Check if bucket exists
aws s3 ls s3://fraudguard-ai-data-971422717446/

# Or find your bucket
aws s3 ls | grep fraudguard
```

---

## Step-by-Step Training Process

### Step 1: Prepare Training Data (If Not Already Done)

**If you already have processed data in S3, skip to Step 2.**

#### 1.1: Process Training Data Locally

```bash
cd /Users/yan/gauntlet/adfraud-aws

# Process TalkingData dataset
python3 scripts/process_training_data.py \
    --data-source talkingdata \
    --output data/training/processed/ \
    --train-size 0.7 \
    --val-size 0.15 \
    --test-size 0.15
```

#### 1.2: Upload Processed Data to S3

```bash
# Upload training data
aws s3 cp data/training/processed/train.csv \
    s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/train.csv

# Upload validation data
aws s3 cp data/training/processed/val.csv \
    s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/val.csv

# Upload test data (optional, for final evaluation)
aws s3 cp data/training/processed/test.csv \
    s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/test.csv
```

**Verify upload:**
```bash
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/
```

**Expected output:**
```
train.csv
val.csv
test.csv
```

---

### Step 2: Calculate Class Imbalance (for scale_pos_weight)

**Important**: Bot traffic is typically a minority class. We need to calculate `scale_pos_weight` to handle class imbalance.

```bash
python3 -c "
import pandas as pd
import numpy as np

# Load training data
df = pd.read_csv('data/training/processed/train.csv', header=None)
y_train = df.iloc[:, -1].values

# Calculate class distribution
num_fraud = y_train.sum()
num_nonfraud = len(y_train) - num_fraud
fraud_rate = num_fraud / len(y_train) * 100

# Calculate scale_pos_weight (AWS best practice)
scale_pos_weight = np.sqrt(num_nonfraud / num_fraud)

print(f'📊 Class Distribution:')
print(f'   Total samples: {len(y_train):,}')
print(f'   Fraud samples: {num_fraud:,} ({fraud_rate:.2f}%)')
print(f'   Non-fraud samples: {num_nonfraud:,} ({100-fraud_rate:.2f}%)')
print(f'   Scale pos weight: {scale_pos_weight:.4f}')
print()
print(f'💡 Use this scale_pos_weight in training: {scale_pos_weight:.4f}')
"
```

**Save the `scale_pos_weight` value** - you'll need it in Step 3.

---

### Step 3: Train Baseline XGBoost Model

#### 3.1: Create Training Script

**File**: `scripts/train_bot_traffic_xgboost.py`

```python
#!/usr/bin/env python3
"""
Train XGBoost model for bot traffic detection in SageMaker
"""

import argparse
import os
import sys
from pathlib import Path

import boto3
import sagemaker
from sagemaker.inputs import TrainingInput
from sagemaker.xgboost.estimator import XGBoost

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def train_bot_traffic_model(
    s3_bucket: str,
    s3_prefix: str,
    sagemaker_role_arn: str,
    scale_pos_weight: float,
    instance_type: str = 'ml.m5.xlarge',
    job_name: str = None
):
    """
    Train XGBoost model optimized for bot traffic detection
    
    Args:
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix for training data (e.g., 'fraud-detection/training/processed/')
        sagemaker_role_arn: IAM role ARN for SageMaker
        scale_pos_weight: Class imbalance weight (from Step 2)
        instance_type: SageMaker instance type
        job_name: Optional training job name
    """
    session = sagemaker.Session()
    
    # S3 paths
    train_path = f's3://{s3_bucket}/{s3_prefix}train.csv'
    val_path = f's3://{s3_bucket}/{s3_prefix}val.csv'
    
    print("=" * 80)
    print("🤖 BOT TRAFFIC DETECTION - XGBoost Training")
    print("=" * 80)
    print()
    print(f"📊 Configuration:")
    print(f"   S3 Bucket: {s3_bucket}")
    print(f"   Training Data: {train_path}")
    print(f"   Validation Data: {val_path}")
    print(f"   Instance Type: {instance_type}")
    print(f"   Scale Pos Weight: {scale_pos_weight:.4f}")
    print()
    
    # Create XGBoost estimator
    # Using script mode with custom training script
    estimator = XGBoost(
        entry_point='xgboost_train.py',
        source_dir='scripts',
        role=sagemaker_role_arn,
        instance_type=instance_type,
        framework_version='1.7-1',
        py_version='py3',
        hyperparameters={
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'num_round': 100,
            'max_depth': 6,
            'eta': 0.3,
            'min_child_weight': 1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'scale_pos_weight': scale_pos_weight,  # Critical for imbalanced data
        },
        output_path=f's3://{s3_bucket}/{s3_prefix}models/',
    )
    
    # Train model
    print("🚀 Starting training job...")
    print(f"   This may take 30-60 minutes")
    print()
    
    estimator.fit(
        {
            'train': TrainingInput(train_path, content_type='text/csv'),
            'validation': TrainingInput(val_path, content_type='text/csv'),
        },
        job_name=job_name,
        wait=True,
        logs=True
    )
    
    print()
    print("=" * 80)
    print("✅ Training Complete!")
    print("=" * 80)
    print()
    print(f"📦 Model Artifact: {estimator.model_data}")
    print(f"📊 Training Job Name: {estimator.latest_training_job.name}")
    print()
    print("💡 Next Steps:")
    print("   1. Review training metrics in CloudWatch")
    print("   2. Run hyperparameter optimization (Step 4)")
    print("   3. Deploy model to endpoint (Step 5)")
    
    return estimator


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train XGBoost model for bot traffic detection')
    parser.add_argument('--s3-bucket', type=str, required=True, help='S3 bucket name')
    parser.add_argument('--s3-prefix', type=str, default='fraud-detection/training/processed/', 
                       help='S3 prefix for training data')
    parser.add_argument('--sagemaker-role-arn', type=str, required=True, 
                       help='SageMaker execution role ARN')
    parser.add_argument('--scale-pos-weight', type=float, required=True,
                       help='Scale pos weight for class imbalance (from Step 2)')
    parser.add_argument('--instance-type', type=str, default='ml.m5.xlarge',
                       help='SageMaker instance type')
    parser.add_argument('--job-name', type=str, default=None,
                       help='Optional training job name')
    
    args = parser.parse_args()
    
    # Ensure prefix ends with /
    if not args.s3_prefix.endswith('/'):
        args.s3_prefix += '/'
    
    train_bot_traffic_model(
        s3_bucket=args.s3_bucket,
        s3_prefix=args.s3_prefix,
        sagemaker_role_arn=args.sagemaker_role_arn,
        scale_pos_weight=args.scale_pos_weight,
        instance_type=args.instance_type,
        job_name=args.job_name
    )
```

#### 3.2: Run Baseline Training

```bash
cd /Users/yan/gauntlet/adfraud-aws

# Replace SCALE_POS_WEIGHT with value from Step 2
python3 scripts/train_bot_traffic_xgboost.py \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --s3-prefix fraud-detection/training/processed/ \
    --sagemaker-role-arn arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role \
    --scale-pos-weight 5.2341 \
    --instance-type ml.m5.xlarge
```

**Expected Duration**: 30-60 minutes

**What happens**:
1. SageMaker launches training instance
2. Downloads training data from S3
3. Trains XGBoost model
4. Uploads model artifact to S3
5. Logs metrics to CloudWatch

**Monitor progress**:
- Watch console output for real-time logs
- Or check CloudWatch: `aws logs tail /aws/sagemaker/TrainingJobs --follow`

---

### Step 4: Hyperparameter Optimization (Recommended)

Optimize hyperparameters specifically for bot traffic detection.

#### 4.1: Use Existing HPO Script

```bash
cd /Users/yan/gauntlet/adfraud-aws

python3 scripts/hpo_xgboost_sagemaker.py \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --s3-prefix fraud-detection/training/processed/ \
    --sagemaker-role-arn arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role \
    --max-jobs 10 \
    --parallel-jobs 2 \
    --instance-type ml.m5.xlarge
```

**Expected Duration**: 2-4 hours (10 jobs × 2 parallel)

**What happens**:
1. Launches 10 training jobs with different hyperparameters
2. Runs 2 jobs in parallel
3. Evaluates each model on validation set
4. Selects best model based on validation AUC

**Monitor progress**:
```bash
# Check tuning job status
aws sagemaker describe-hyper-parameter-tuning-job \
    --hyper-parameter-tuning-job-name <JOB_NAME>
```

---

### Step 5: Evaluate Model Performance

#### 5.1: Get Best Model from HPO

```bash
# List training jobs from HPO
aws sagemaker list-training-jobs-for-hyper-parameter-tuning-job \
    --hyper-parameter-tuning-job-name <HPO_JOB_NAME> \
    --sort-by FinalObjectiveMetricValue \
    --sort-order Descending \
    --max-results 1
```

#### 5.2: Evaluate on Test Set

```bash
python3 scripts/evaluate_model.py \
    --training-job-name <BEST_TRAINING_JOB_NAME> \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --test-data s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/test.csv
```

**Expected Metrics** (for bot traffic detection):
- **Precision**: > 0.85 (low false positives)
- **Recall**: > 0.80 (catch most bots)
- **F1 Score**: > 0.82
- **ROC AUC**: > 0.95

---

### Step 6: Deploy Model to SageMaker Endpoint

#### 6.1: Create Deployment Script

**File**: `scripts/deploy_bot_traffic_model.py`

```python
#!/usr/bin/env python3
"""
Deploy trained XGBoost model to SageMaker endpoint for bot traffic detection
"""

import argparse
import sagemaker
from sagemaker.xgboost.model import XGBoostModel
from sagemaker.serializers import CSVSerializer
from sagemaker.deserializers import CSVDeserializer


def deploy_model(
    model_s3_path: str,
    sagemaker_role_arn: str,
    endpoint_name: str,
    instance_type: str = 'ml.t2.medium'
):
    """
    Deploy XGBoost model to SageMaker endpoint
    
    Args:
        model_s3_path: S3 path to model artifact (model.tar.gz)
        sagemaker_role_arn: IAM role ARN
        endpoint_name: Name for the endpoint
        instance_type: Instance type for endpoint
    """
    session = sagemaker.Session()
    
    print("=" * 80)
    print("🚀 DEPLOYING BOT TRAFFIC DETECTION MODEL")
    print("=" * 80)
    print()
    print(f"📦 Model: {model_s3_path}")
    print(f"🎯 Endpoint: {endpoint_name}")
    print(f"💻 Instance: {instance_type}")
    print()
    
    # Create model
    model = XGBoostModel(
        model_data=model_s3_path,
        role=sagemaker_role_arn,
        framework_version='1.7-1',
        py_version='py3',
    )
    
    # Deploy endpoint
    print("⏳ Deploying endpoint (this may take 5-10 minutes)...")
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name,
        serializer=CSVSerializer(),
        deserializer=CSVDeserializer()
    )
    
    print()
    print("=" * 80)
    print("✅ Endpoint Deployed Successfully!")
    print("=" * 80)
    print()
    print(f"🔗 Endpoint Name: {endpoint_name}")
    print(f"📊 Endpoint ARN: {predictor.endpoint_name}")
    print()
    print("💡 Next Steps:")
    print("   1. Update Lambda environment variable: SAGEMAKER_ENDPOINT=" + endpoint_name)
    print("   2. Test endpoint with sample requests")
    print("   3. Monitor endpoint metrics in CloudWatch")
    
    return predictor


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Deploy XGBoost model for bot traffic detection')
    parser.add_argument('--model-s3-path', type=str, required=True,
                       help='S3 path to model artifact (e.g., s3://bucket/path/model.tar.gz)')
    parser.add_argument('--sagemaker-role-arn', type=str, required=True,
                       help='SageMaker execution role ARN')
    parser.add_argument('--endpoint-name', type=str, required=True,
                       help='Endpoint name (e.g., fraudguard-bot-detection-endpoint)')
    parser.add_argument('--instance-type', type=str, default='ml.t2.medium',
                       help='Instance type for endpoint')
    
    args = parser.parse_args()
    
    deploy_model(
        model_s3_path=args.model_s3_path,
        sagemaker_role_arn=args.sagemaker_role_arn,
        endpoint_name=args.endpoint_name,
        instance_type=args.instance_type
    )
```

#### 6.2: Deploy Endpoint

```bash
# Get model path from training job
MODEL_S3_PATH="s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/models/<TRAINING_JOB_NAME>/output/model.tar.gz"

python3 scripts/deploy_bot_traffic_model.py \
    --model-s3-path "$MODEL_S3_PATH" \
    --sagemaker-role-arn arn:aws:iam::971422717446:role/fraudguard-ai-sagemaker-execution-role \
    --endpoint-name fraudguard-bot-detection-endpoint \
    --instance-type ml.t2.medium
```

**Expected Duration**: 5-10 minutes

---

### Step 7: Test Endpoint

#### 7.1: Test with Sample Features

```python
import boto3
import json

# Create SageMaker runtime client
runtime = boto3.client('sagemaker-runtime')

# Sample feature vector (29 features in order)
# This represents a suspicious bot-like event
sample_features = [
    10.0,   # ip_click_count_24h (high)
    5.0,    # device_click_count_1h (high)
    2.0,    # time_since_last_click (very short)
    14,     # hour_of_day
    2,      # day_of_week
    1.0,    # ua_is_bot (True - bot detected)
    0.2,    # ua_entropy (low - suspicious)
    0.0,    # ip_is_datacenter
    0.0,    # ip_is_vpn
    0.0,    # ip_is_proxy
    0.0,    # ip_is_business
    0.0,    # ip_is_competitor
    0.0,    # geo_distance_km
    0.0,    # referrer_is_valid (False - no referrer)
    50,     # click_to_view_time_ms (very short)
    0.1,    # campaign_fraud_rate
    0.3,    # publisher_quality (low)
    0.2,    # device_fingerprint_entropy (low)
    0.0,    # is_mobile
    0.0,    # is_repeated_click
    0.0,    # time_to_conversion_sec
    0,      # ip_country_encoded
    0,      # device_os_encoded
    0.0,    # click_to_install_time_sec
    0.0,    # has_recent_install
    0.0,    # install_broadcast_detected
    0.0,    # click_injection_risk_score
    0.0,    # conversion_rate
    0.1,    # engagement_score (low)
]

# Convert to CSV format
feature_csv = ','.join(map(str, sample_features))

# Invoke endpoint
response = runtime.invoke_endpoint(
    EndpointName='fraudguard-bot-detection-endpoint',
    ContentType='text/csv',
    Body=feature_csv
)

# Parse response
prediction = float(response['Body'].read().decode('utf-8').strip())
print(f"Bot Traffic Score: {prediction:.4f}")
print(f"Prediction: {'BOT' if prediction > 0.5 else 'LEGITIMATE'}")
```

#### 7.2: Test with Real Data

```bash
python3 scripts/evaluate_model.py \
    --endpoint-name fraudguard-bot-detection-endpoint \
    --test-data data/training/processed/test.csv \
    --sample-size 100
```

---

### Step 8: Update Lambda to Use New Endpoint

#### 8.1: Update Environment Variable

**In `template.yaml` or Lambda console:**

```yaml
Environment:
  Variables:
    SAGEMAKER_ENDPOINT: fraudguard-bot-detection-endpoint
```

#### 8.2: Deploy Updated Lambda

```bash
sam build && sam deploy
```

---

## Bot Traffic Detection Optimization Tips

### 1. Feature Importance Analysis

After training, analyze which features are most important for bot detection:

```python
import boto3
import json

# Get feature importance from training job
s3_client = boto3.client('s3')
# Download model and extract feature importance
# (XGBoost stores this in the model artifact)
```

### 2. Threshold Tuning for Bot Detection

Bot traffic detection may benefit from a **lower threshold** (0.3-0.4) to catch more bots:

```python
# In your Lambda function
BOT_DETECTION_THRESHOLD = 0.35  # Lower than general fraud threshold

if ml_score >= BOT_DETECTION_THRESHOLD:
    # Flag as bot traffic
    is_bot = True
```

### 3. Focus on Bot-Specific Features

Monitor these features in production:
- `ua_is_bot` - Direct bot detection
- `ua_entropy` - Low entropy = suspicious
- `ip_click_count_24h` - High counts = automation
- `device_click_count_1h` - Rapid clicks = bot

---

## Troubleshooting

### Issue: Training Job Fails

**Check logs:**
```bash
aws logs tail /aws/sagemaker/TrainingJobs/<JOB_NAME> --follow
```

**Common issues:**
- **S3 access denied**: Check IAM role permissions
- **Data format error**: Verify CSV format (no headers, label in last column)
- **Out of memory**: Use larger instance type (`ml.m5.2xlarge`)

### Issue: Endpoint Creation Fails

**Check endpoint logs:**
```bash
aws logs tail /aws/sagemaker/Endpoints/<ENDPOINT_NAME> --follow
```

**Common issues:**
- **Model artifact not found**: Verify S3 path
- **Role permissions**: Check SageMaker role has endpoint creation permissions

### Issue: Low Bot Detection Performance

**Solutions:**
1. Increase training data (especially bot samples)
2. Adjust `scale_pos_weight` (try higher values)
3. Run HPO with more jobs
4. Lower classification threshold

---

## Cost Estimates

### Training
- **Baseline Training**: `ml.m5.xlarge` × 1 hour = ~$0.23
- **HPO (10 jobs)**: `ml.m5.xlarge` × 10 hours = ~$2.30

### Endpoint
- **Development**: `ml.t2.medium` = ~$0.065/hour (~$47/month)
- **Production**: `ml.m5.large` = ~$0.115/hour (~$83/month)

---

## Quick Reference Commands

```bash
# 1. Calculate scale_pos_weight
python3 -c "import pandas as pd; import numpy as np; df = pd.read_csv('data/training/processed/train.csv', header=None); y = df.iloc[:, -1]; print(f'scale_pos_weight: {np.sqrt((len(y) - y.sum()) / y.sum()):.4f}')"

# 2. Train baseline model
python3 scripts/train_bot_traffic_xgboost.py \
    --s3-bucket <BUCKET> \
    --sagemaker-role-arn <ROLE_ARN> \
    --scale-pos-weight <WEIGHT>

# 3. Run HPO
python3 scripts/hpo_xgboost_sagemaker.py \
    --s3-bucket <BUCKET> \
    --sagemaker-role-arn <ROLE_ARN> \
    --max-jobs 10

# 4. Deploy endpoint
python3 scripts/deploy_bot_traffic_model.py \
    --model-s3-path <MODEL_PATH> \
    --sagemaker-role-arn <ROLE_ARN> \
    --endpoint-name fraudguard-bot-detection-endpoint
```

---

## Next Steps

1. ✅ Train baseline model (Step 3)
2. ✅ Run hyperparameter optimization (Step 4)
3. ✅ Evaluate model performance (Step 5)
4. ✅ Deploy to endpoint (Step 6)
5. ✅ Test with real data (Step 7)
6. ✅ Update Lambda configuration (Step 8)
7. ✅ Monitor production performance

---

## References

- [XGBoost Training Guide](docs/XGBOOST_TRAINING_GUIDE.md)
- [SageMaker Processing Workflow](docs/SAGEMAKER_PROCESSING_WORKFLOW.md)
- [Features by Fraud Type](docs/FEATURES_BY_FRAUD_TYPE.md)

