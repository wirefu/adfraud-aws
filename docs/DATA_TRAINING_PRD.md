# Data Training PRD: Fraud Detection Model Training Pipeline

**Version**: 1.0  
**Date**: November 2024  
**Status**: Draft  
**Owner**: ML Engineering Team

---

## 1. Executive Summary

This PRD defines the requirements for preparing training data and training the XGBoost fraud detection model for the FraudGuard AI system. The goal is to create a production-ready machine learning model that can accurately detect fraudulent ad clicks in real-time across multiple ad platforms (Google Ads, Meta Ads, LinkedIn Ads, etc.).

### Multi-Platform Support

The system is designed to support multiple ad platforms through a platform abstraction layer:
- **Google Ads**: Parallel tracking integration (limited signals)
- **Meta Ads**: Facebook/Instagram server-side events
- **LinkedIn Ads**: LinkedIn Marketing API integration
- **Extensible**: Additional platforms can be added via platform adapters

Each platform has platform-specific features (e.g., GCLID for Google, FBCLID for Meta) while maintaining a consistent feature vector for the ML model.

### Objectives

1. **Prepare labeled training data** from multiple sources (TalkingData, FDB, synthetic, multi-platform historical data)
2. **Engineer features** that match the production feature extractor (supports multi-platform)
3. **Train XGBoost model** using SageMaker with best practices
4. **Optimize model performance** using hyperparameter tuning
5. **Deploy model** to SageMaker endpoint for real-time inference
6. **Establish retraining pipeline** for continuous improvement

### Success Criteria

- ✅ Minimum 100,000 labeled training samples
- ✅ Model performance: Cohen's Kappa > 0.75 (target: > 0.88 with HPO)
- ✅ Model performance: F1 Score > 0.75 (target: > 0.88 with HPO)
- ✅ Model performance: ROC AUC > 0.95
- ✅ Inference latency < 100ms
- ✅ Model deployed to SageMaker endpoint
- ✅ Retraining pipeline operational

### AWS Resources Overview

**Existing Resources** (Available Now):
- ✅ **S3 Bucket** (`DataBucket`) - For training data and model artifacts
- ✅ **DynamoDB Table** - For event storage (can extract training data)
- ✅ **Lambda Functions** - Can be used for data processing
- ✅ **CloudWatch Logs** - For monitoring

**New Resources Required**:
- ⏳ **SageMaker Execution Role** - IAM role for SageMaker operations
- ⏳ **Data Processing Lambda** (optional) - Process training data
- ⏳ **SageMaker Endpoint** - Real-time inference endpoint (after training)

**See Section 7** for detailed AWS infrastructure architecture and implementation plan.

---

## 2. Data Sources

### 2.1 Primary Data Source: TalkingData AdTracking Fraud Detection

**Status**: ✅ Available (185M records extracted)

**Location**: `data/talkingdata/`

**Files**:
- `train.csv` - 7.0 GB, 184,903,891 rows (primary training data)
- `train_sample.csv` - 3.9 MB, 100,001 rows (for development/testing)
- `test.csv` - 823 MB (evaluation data)
- `test_supplement.csv` - 2.5 GB (additional evaluation data)

**Schema**:
- `ip` - IP address (integer encoded)
- `app` - App ID
- `device` - Device ID
- `os` - Operating system version
- `channel` - Channel ID
- `click_time` - Timestamp of click
- `attributed_time` - Timestamp of attribution (if attributed)
- `is_attributed` - Label (0 = fraud, 1 = legitimate)

**Label Mapping**:
```python
is_fraud = 1 - is_attributed  # Invert: 0=legitimate, 1=fraud
```

**Usage**: Primary training dataset (meets 100k+ requirement)

### 2.2 Secondary Data Source: FDB (Fraud Dataset Benchmark)

**Status**: ⏳ Framework available, datasets need Kaggle API download

**Location**: `data/fdb/fraud-dataset-benchmark-main/`

**Available Datasets** (9 total):
1. IEEE-CIS Fraud Detection - 561,013 train samples (3.50% fraud)
2. Credit Card Fraud Detection - 227,845 train samples (0.18% fraud)
3. Fraud ecommerce - 120,889 train samples (10.60% fraud)
4. Simulated Credit Card Transactions (Sparkov) - 1,296,675 train samples (5.70% fraud)
5. Twitter Bot Accounts - 29,950 train samples (33.10% fraud)
6. Malicious URLs - 586,072 train samples (34.20% fraud)
7. Fake Job Posting Prediction - 14,304 train samples (4.70% fraud)
8. Vehicle Loan Default Prediction - 186,523 train samples (21.60% fraud)
9. IP Blocklist - 172,000 train samples (7% fraud)

**Usage**: Supplementary training data, domain adaptation, benchmarking

### 2.3 Tertiary Data Source: Synthetic Data

**Status**: 📝 Code example available, not generated

**Location**: Code in PRD (lines 2135-2182), output would be `data/synthetic/`

**Capabilities**:
- Generate 100k+ samples
- Configurable class balance (default: 70% legitimate, 30% fraud)
- Fraud patterns: bot traffic, click farms, device farms

**Usage**: Quick start, data augmentation, testing

### 2.4 Domain Data: Historical Multi-Platform Ad Data

**Status**: ⏳ Scripts available, data not imported/labeled

**Location**: DynamoDB (after import via platform-specific scripts)

**Supported Platforms**:
1. **Google Ads** - `scripts/import_historical_google_ads_data.py`
   - Date range: Nov 2023 to Nov 2024 (shifted forward)
   - Source: Google Ads API
   - Includes: Campaign performance, keywords, placements, click details
2. **Meta Ads** (Facebook/Instagram) - To be implemented
   - Source: Meta Conversions API / Marketing API
   - Includes: Campaign performance, placements, audience data
3. **LinkedIn Ads** - To be implemented
   - Source: LinkedIn Marketing API
   - Includes: Campaign performance, audience data, creative data
4. **Other Platforms** - Extensible via platform adapters

**Usage**: Domain-specific training data (requires labeling)

---

## 3. Data Preparation Requirements

### 3.1 Data Quality Standards

**Minimum Requirements**:
- ✅ 100,000+ labeled samples (TalkingData provides 185M)
- ✅ Class balance: 70% legitimate, 30% fraud (or use SMOTE)
- ✅ No missing critical features
- ✅ Consistent feature encoding

**Data Validation**:
- Check for duplicate records
- Validate label distribution
- Verify feature ranges
- Check for data leakage (temporal splits)

### 3.2 Data Splitting Strategy

**Split Ratios**: 70% train, 15% validation, 15% test

**Splitting Method**: Stratified sampling (maintain class balance)

**Temporal Considerations**:
- If time-based features exist, use temporal split (train on older data, test on newer)
- For TalkingData: Use `click_time` for temporal ordering

**Implementation**:
```python
from sklearn.model_selection import train_test_split

# First split: 70% train, 30% temp
X_train, X_temp, y_train, y_temp = train_test_split(
    features, labels, test_size=0.3, stratify=labels, random_state=42
)

# Second split: 15% validation, 15% test
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42
)
```

### 3.3 Feature Engineering Requirements

**Critical**: Features must match `src/orchestrator/feature_extractor.py` exactly

**Required Features** (20+ total, in exact order):

1. **Behavioral Features**:
   - `ip_click_count_24h` - Clicks from IP in last 24 hours
   - `device_click_count_1h` - Clicks from device in last hour
   - `time_since_last_click` - Seconds since last click

2. **Temporal Features**:
   - `hour_of_day` - Hour of day (0-23)
   - `day_of_week` - Day of week (0-6)

3. **User Agent Features** (if available):
   - `ua_is_bot` - Boolean (user agent contains bot keywords)
   - `ua_entropy` - String complexity (0-1)

4. **IP Reputation Features**:
   - `ip_is_datacenter` - Boolean (IP in datacenter range)
   - `ip_is_vpn` - Boolean (IP is known VPN)
   - `ip_is_proxy` - Boolean (IP is proxy)
   - `ip_is_business` - Boolean (IP is business)
   - `ip_is_competitor` - Boolean (IP is competitor)
   - `geo_distance_km` - Geographic distance

5. **Context Features**:
   - `referrer_is_valid` - Boolean (valid referrer domain)
   - `click_to_view_time_ms` - Time on page before click

6. **Historical Features**:
   - `campaign_fraud_rate` - Historical fraud rate for campaign
   - `publisher_quality` - Publisher quality score (0-1)
   - **Platform-Specific**:
     - `keyword_fraud_rate` - Google Ads keyword fraud rate
     - `target_fraud_rate` - Google Ads target/placement fraud rate
     - `placement_fraud_rate` - Meta Ads placement fraud rate
     - `audience_fraud_rate` - LinkedIn Ads audience fraud rate
     - `gclid_pattern_score` - Google Ads GCLID pattern analysis
     - `fbclid_pattern_score` - Meta Ads FBCLID pattern analysis

7. **Device Features**:
   - `device_fingerprint_entropy` - Device uniqueness score
   - `is_mobile` - Boolean (mobile device)
   - `is_repeated_click` - Boolean (duplicate click ID)

8. **Conversion Features**:
   - `time_to_conversion_sec` - Time to conversion

9. **Encoded Features**:
   - `ip_country_encoded` - Country code (encoded)
   - `device_os_encoded` - Operating system (encoded)

10. **Click Injection Features** (new):
    - `click_to_install_time_sec` - Time between click and install
    - `has_recent_install` - Boolean
    - `install_broadcast_detected` - Boolean
    - `click_injection_risk_score` - Risk score

11. **Engagement Features** (new):
    - `conversion_rate` - Conversion rate
    - `engagement_score` - Engagement score

**Feature Engineering Pipeline**:

```python
def engineer_features(talkingdata_df):
    """
    Convert TalkingData format to production feature format
    """
    features = []
    
    # 1. Aggregate features (IP click counts, device click counts)
    # 2. Temporal features (from click_time)
    # 3. IP reputation (if available, else defaults)
    # 4. Device features (from device, os columns)
    # 5. Map to exact feature order
    
    return feature_matrix
```

### 3.4 Data Preprocessing

**Handling Missing Values**:
- Numerical: Fill with 0 or median
- Categorical: Fill with mode or "unknown"
- Temporal: Use default timestamps

**Feature Scaling**:
- XGBoost doesn't require scaling, but ensure:
  - All features are numerical
  - No infinite values
  - Reasonable value ranges

**Categorical Encoding**:
- One-hot encode or label encode categorical features
- Ensure consistent encoding between train/test

**Class Imbalance Handling**:
- **Option 1**: XGBoost `scale_pos_weight` parameter
  ```python
  scale_pos_weight = sqrt(num_nonfraud / num_fraud)
  ```
- **Option 2**: SMOTE (Synthetic Minority Over-sampling)
  ```python
  from imblearn.over_sampling import SMOTE
  smote = SMOTE(random_state=42)
  X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
  ```

---

## 4. Model Training Requirements

### 4.1 Model Specifications

**Algorithm**: XGBoost (Gradient Boosted Trees)

**Type**: Binary Classifier

**Framework**: SageMaker Built-in XGBoost Algorithm

**Version**: `framework_version='1.7-1'`

### 4.2 Training Infrastructure

**SageMaker Configuration**:
- **Training Instance**: `ml.m5.xlarge` (or `ml.m5.2xlarge` for large datasets)
- **Instance Count**: 1
- **Training Timeout**: 24 hours
- **Output Path**: `s3://{bucket}/{prefix}/models/`

**Data Storage**:
- **S3 Bucket**: Configured via environment variable
- **S3 Prefix**: `fraud-detection/training/`
- **Format**: CSV (SageMaker XGBoost expects CSV)

### 4.3 Hyperparameters

**Baseline Hyperparameters**:
```python
{
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'num_round': 100,
    'max_depth': 6,
    'eta': 0.3,
    'gamma': 0,
    'min_child_weight': 1,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'scale_pos_weight': <calculated>  # Based on class imbalance
}
```

**Hyperparameter Optimization (HPO) Ranges**:
```python
{
    'num_round': IntegerParameter(50, 200),
    'max_depth': IntegerParameter(3, 10),
    'eta': ContinuousParameter(0.01, 0.3),
    'gamma': ContinuousParameter(0, 5),
    'min_child_weight': IntegerParameter(1, 10),
    'subsample': ContinuousParameter(0.5, 1.0),
    'colsample_bytree': ContinuousParameter(0.5, 1.0),
}
```

**HPO Configuration**:
- **Objective Metric**: `validation:auc` (maximize)
- **Max Jobs**: 10
- **Max Parallel Jobs**: 2
- **Early Stopping**: Auto

### 4.4 Training Pipeline

**Step 1: Data Preparation**
- Load TalkingData (start with sample, then full)
- Engineer features to match production extractor
- Handle class imbalance
- Split into train/val/test (70/15/15)
- Upload to S3

**Step 2: Baseline Training**
- Train XGBoost with baseline hyperparameters
- Use `scale_pos_weight` for class imbalance
- Evaluate on validation set
- Save baseline metrics

**Step 3: Hyperparameter Optimization**
- Run HPO tuning job
- Train 10 models with different hyperparameters
- Select best model based on validation AUC
- Evaluate best model on test set

**Step 4: Model Evaluation**
- Calculate metrics: Balanced Accuracy, Cohen's Kappa, F1, ROC AUC
- Generate confusion matrix
- Analyze feature importance
- Compare baseline vs optimized model

**Step 5: Model Deployment**
- Deploy best model to SageMaker endpoint
- Instance type: `ml.t2.medium` (dev) or `ml.m5.large` (production)
- Configure auto-scaling
- Test endpoint with sample requests

**Step 6: Integration**
- Update Lambda environment variable: `SAGEMAKER_ENDPOINT`
- Test end-to-end fraud detection
- Monitor endpoint metrics

---

## 5. Evaluation Criteria

### 5.1 Performance Metrics

**Primary Metrics**:
1. **Cohen's Kappa** - Target: > 0.75 (with HPO: > 0.88)
2. **F1 Score** - Target: > 0.75 (with HPO: > 0.88)
3. **ROC AUC** - Target: > 0.95
4. **Balanced Accuracy** - Target: > 0.85 (with HPO: > 0.90)

**Secondary Metrics**:
- Precision (fraud class)
- Recall (fraud class)
- False Positive Rate
- False Negative Rate

**Confusion Matrix Analysis**:
- True Negatives (correctly identified legitimate)
- False Positives (legitimate flagged as fraud)
- False Negatives (fraud missed)
- True Positives (correctly identified fraud)

### 5.2 Operational Metrics

**Inference Performance**:
- Latency: < 100ms (p95)
- Throughput: > 1000 requests/second
- Error Rate: < 0.1%

**Cost Metrics**:
- Training Cost: < $10 per training run
- Endpoint Cost: < $100/month (dev), < $200/month (production)

### 5.3 Model Validation

**Cross-Validation**:
- Use stratified k-fold (k=5) for additional validation
- Ensure consistent performance across folds

**Temporal Validation**:
- If using temporal split, validate on future data
- Check for model drift over time

**A/B Testing** (Future):
- Compare new model vs current model
- Deploy gradually (10% → 50% → 100% traffic)

---

## 6. Implementation Plan

### 6.1 Phase 1: Data Preparation (Week 1)

**Tasks**:
1. ✅ Extract TalkingData dataset (DONE)
2. ⏳ Create feature engineering script
3. ⏳ Map TalkingData to production features
4. ⏳ Handle missing features (IP reputation, user agent, etc.)
5. ⏳ Generate synthetic data (optional, for augmentation)
6. ⏳ Validate data quality
7. ⏳ Split data (train/val/test)

**Deliverables**:
- Feature engineering script
- Processed training data (CSV format)
- Data validation report
- Data split files in S3

### 6.2 Phase 2: Baseline Training (Week 1-2)

**Tasks**:
1. ⏳ Set up SageMaker training job
2. ⏳ Train baseline XGBoost model
3. ⏳ Evaluate baseline performance
4. ⏳ Document baseline metrics
5. ⏳ Analyze feature importance

**Deliverables**:
- Baseline model artifact
- Baseline performance metrics
- Feature importance analysis
- Training logs

### 6.3 Phase 3: Hyperparameter Optimization (Week 2)

**Tasks**:
1. ⏳ Configure HPO tuning job
2. ⏳ Run HPO (10 models, 2 parallel)
3. ⏳ Select best model
4. ⏳ Evaluate best model on test set
5. ⏳ Compare baseline vs optimized

**Deliverables**:
- Optimized model artifact
- HPO results and analysis
- Performance comparison report
- Best hyperparameters

### 6.4 Phase 4: Model Deployment (Week 2)

**Tasks**:
1. ⏳ Deploy model to SageMaker endpoint
2. ⏳ Configure auto-scaling
3. ⏳ Test endpoint with sample requests
4. ⏳ Measure inference latency
5. ⏳ Update Lambda environment variables
6. ⏳ Test end-to-end integration

**Deliverables**:
- Live SageMaker endpoint
- Endpoint configuration
- Integration test results
- Performance benchmarks

### 6.5 Phase 5: Retraining Pipeline (Week 3)

**Tasks**:
1. ⏳ Design retraining workflow
2. ⏳ Set up EventBridge schedule (weekly)
3. ⏳ Create retraining Lambda function
4. ⏳ Implement model versioning
5. ⏳ Set up model evaluation automation
6. ⏳ Configure blue-green deployment

**Deliverables**:
- Automated retraining pipeline
- Model versioning system
- Evaluation automation
- Deployment automation

---

## 7. AWS Infrastructure & Resources

### 7.1 Existing AWS Resources (Available Now)

**S3 Bucket**:
- **Resource**: `DataBucket` (defined in `template.yaml`)
- **Name**: `{StackName}-data-{AccountId}`
- **Purpose**: Store training data, model artifacts, processed datasets
- **Features**:
  - Versioning enabled
  - Lifecycle rules (archive to Glacier after 90 days)
  - Encryption (AES256)
  - Private access only
- **S3 Paths**:
  - Training data: `s3://{bucket}/fraud-detection/training/`
  - Model artifacts: `s3://{bucket}/fraud-detection/models/`
  - Processed data: `s3://{bucket}/fraud-detection/processed/`

**Lambda Functions** (can be reused):
- **IngestionHandler**: Can process data uploads
- **Orchestrator**: Has S3 access permissions
- **All Lambdas**: Have `S3_BUCKET_NAME` environment variable

**DynamoDB Table**:
- **Resource**: `EventsTable`
- **Purpose**: Store event data (can be used for training data extraction)
- **Note**: Can query historical events for training

**CloudWatch Logs**:
- Log groups exist for all Lambda functions
- Can monitor training pipeline execution

### 7.2 New AWS Resources Required

#### 7.2.1 SageMaker Execution Role

**Purpose**: IAM role for SageMaker to access S3, create endpoints, run training jobs

**Permissions Needed**:
- S3 read/write access to DataBucket
- SageMaker training job creation
- SageMaker endpoint creation/management
- CloudWatch logs write access

**Implementation**: Add to `template.yaml`

#### 7.2.2 Data Processing Lambda Function

**Purpose**: Process TalkingData, engineer features, upload to S3

**Configuration**:
- **Runtime**: Python 3.11
- **Memory**: 3008 MB (for large dataset processing)
- **Timeout**: 15 minutes (900 seconds)
- **Environment Variables**:
  - `S3_BUCKET_NAME`: DataBucket name
  - `S3_PREFIX`: `fraud-detection/training/`
  - `FEATURE_COUNT`: Number of features (20+)

**Trigger Options**:
- Manual invocation (for initial processing)
- S3 event (when new data uploaded)
- EventBridge schedule (for retraining)

**Implementation**: Add to `template.yaml`

#### 7.2.3 SageMaker Training Job (Infrastructure)

**Note**: Training jobs are created programmatically, not via CloudFormation

**Resources Created at Runtime**:
- SageMaker Training Job
- SageMaker Hyperparameter Tuning Job
- SageMaker Model (after training)
- SageMaker Endpoint Configuration
- SageMaker Endpoint

**Storage**:
- Training data: S3 (DataBucket)
- Model artifacts: S3 (DataBucket)
- Training logs: CloudWatch Logs

#### 7.2.4 SageMaker Endpoint (After Training)

**Purpose**: Real-time inference for fraud detection

**Configuration**:
- **Instance Type**: `ml.t2.medium` (dev) or `ml.m5.large` (production)
- **Initial Instance Count**: 1
- **Auto Scaling**: Enabled (target 70% CPU)
- **Endpoint Name**: `fraudguard-xgboost-endpoint`

**Implementation**: Add to `template.yaml` (uncomment and update)

#### 7.2.5 Step Functions State Machine (Optional)

**Purpose**: Orchestrate training pipeline

**Workflow**:
1. Trigger data processing Lambda
2. Wait for S3 data upload completion
3. Start SageMaker training job
4. Wait for training completion
5. Start HPO job (if enabled)
6. Wait for HPO completion
7. Deploy best model to endpoint
8. Run evaluation
9. Send notification (SNS)

**Alternative**: Use EventBridge + Lambda for simpler orchestration

### 7.3 AWS Resource Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Processing Layer                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Local/EC2                    Lambda Function               │
│  ┌──────────┐                ┌──────────────┐              │
│  │TalkingData│ ──upload──→   │ Data Processor│             │
│  │  CSV      │                │  (Feature Eng)│             │
│  └──────────┘                └──────┬───────┘              │
│                                      │                       │
│                                      ▼                       │
│                              ┌──────────────┐              │
│                              │  S3 Bucket    │              │
│                              │  (DataBucket) │              │
│                              │  /training/   │              │
│                              └──────┬───────┘              │
└─────────────────────────────────────┼───────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────┐
│            Model Training Layer      │                       │
├─────────────────────────────────────┼───────────────────────┤
│                                      │                       │
│                              ┌───────▼────────┐             │
│                              │ SageMaker      │             │
│                              │ Training Job   │             │
│                              │ (XGBoost)      │             │
│                              └───────┬────────┘             │
│                                      │                       │
│                              ┌───────▼────────┐             │
│                              │ SageMaker HPO  │             │
│                              │ (10 models)    │             │
│                              └───────┬────────┘             │
│                                      │                       │
│                              ┌───────▼────────┐             │
│                              │ Model Artifact │             │
│                              │ (S3)           │             │
│                              └───────┬────────┘             │
└──────────────────────────────────────┼──────────────────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────┐
│         Model Deployment Layer        │                      │
├──────────────────────────────────────┼──────────────────────┤
│                                       │                      │
│                              ┌────────▼─────────┐            │
│                              │ SageMaker       │            │
│                              │ Endpoint        │            │
│                              │ (ml.t2.medium)  │            │
│                              └────────┬────────┘            │
│                                       │                      │
│                              ┌────────▼─────────┐            │
│                              │ Lambda           │            │
│                              │ Orchestrator     │            │
│                              │ (Calls Endpoint) │            │
│                              └──────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### 7.4 S3 Data Organization

**Bucket Structure**:
```
s3://{DataBucket}/
├── fraud-detection/
│   ├── training/
│   │   ├── raw/
│   │   │   ├── talkingdata/
│   │   │   │   ├── train.csv
│   │   │   │   └── test.csv
│   │   │   └── fdb/
│   │   ├── processed/
│   │   │   ├── train.csv
│   │   │   ├── val.csv
│   │   │   └── test.csv
│   │   └── features/
│   │       └── feature_mapping.json
│   ├── models/
│   │   ├── xgboost/
│   │   │   ├── baseline/
│   │   │   │   └── model.tar.gz
│   │   │   └── hpo/
│   │   │       └── best-model.tar.gz
│   │   └── metadata/
│   │       └── model_metrics.json
│   └── artifacts/
│       └── training-logs/
```

### 7.5 IAM Permissions Required

**SageMaker Execution Role**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${DataBucket}/*",
        "arn:aws:s3:::${DataBucket}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sagemaker:CreateTrainingJob",
        "sagemaker:CreateHyperParameterTuningJob",
        "sagemaker:CreateModel",
        "sagemaker:CreateEndpointConfig",
        "sagemaker:CreateEndpoint",
        "sagemaker:DescribeTrainingJob",
        "sagemaker:DescribeHyperParameterTuningJob",
        "sagemaker:DescribeModel",
        "sagemaker:DescribeEndpoint",
        "sagemaker:InvokeEndpoint",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Data Processing Lambda Role**:
- S3 read/write to DataBucket
- CloudWatch Logs write
- (Optional) SageMaker read (to check training status)

### 7.6 Cost Estimation

**S3 Storage**:
- Training data: ~11 GB × $0.023/GB = $0.25/month
- Model artifacts: ~100 MB × $0.023/GB = $0.002/month
- **Total S3**: ~$0.25/month

**SageMaker Training**:
- Baseline training: `ml.m5.xlarge` × 1 hour × $0.23/hour = $0.23
- HPO (10 jobs, 2 parallel): `ml.m5.xlarge` × 5 hours × $0.23/hour = $1.15
- **Total Training**: ~$1.38 (one-time)

**SageMaker Endpoint**:
- Dev: `ml.t2.medium` × 730 hours × $0.065/hour = $47.45/month
- Production: `ml.m5.large` × 730 hours × $0.115/hour = $83.95/month

**Lambda (Data Processing)**:
- Processing 185M records: ~1000 invocations × $0.20/1M requests = $0.0002
- Compute: ~100 GB-seconds × $0.0000166667/GB-second = $0.0017
- **Total Lambda**: ~$0.002 (one-time)

**Total Estimated Cost**:
- **One-time Setup**: ~$1.40 (training + processing)
- **Monthly (Dev)**: ~$48 (endpoint + S3)
- **Monthly (Production)**: ~$84 (endpoint + S3)

## 8. Technical Specifications

### 8.1 Feature Engineering Script

**Input**: TalkingData CSV files
**Output**: Processed CSV with features matching `feature_extractor.py`

**Key Functions**:
- `load_talkingdata()` - Load and parse TalkingData
- `compute_aggregated_features()` - IP/device click counts
- `extract_temporal_features()` - Hour, day of week
- `add_ip_reputation()` - IP reputation features (if available)
- `map_to_production_features()` - Match exact feature order
- `handle_missing_features()` - Default values for unavailable features

**AWS Implementation**:
- **Location**: Lambda function or SageMaker Processing Job
- **Storage**: S3 (DataBucket)
- **Processing**: Chunked processing for large files (185M records)

### 8.2 Training Script

**Location**: `scripts/train_xgboost_sagemaker.py`

**Key Functions**:
- `load_training_data()` - Load from S3 or local
- `prepare_features_and_labels()` - Feature engineering
- `split_data()` - Train/val/test split
- `apply_smote()` - Handle class imbalance (optional)
- `upload_data_to_s3()` - Upload for SageMaker
- `train_xgboost_baseline()` - Baseline training
- `train_xgboost_with_hpo()` - HPO training
- `evaluate_model()` - Model evaluation
- `deploy_model()` - Deploy to endpoint

**AWS Implementation Options**:

**Option 1: Local/EC2 Execution** (Recommended for initial training)
- Run script on local machine or EC2 instance
- Requires AWS credentials configured
- Direct SageMaker SDK access
- Full control over process

**Option 2: Lambda Function** (For automation)
- Create Lambda function for training orchestration
- Triggered by EventBridge schedule or S3 event
- Limitations: 15-minute timeout (use async for long jobs)
- Use Step Functions for multi-step workflow

**Option 3: SageMaker Processing Job** (For large-scale processing)
- Use SageMaker Processing for data preparation
- Use SageMaker Training for model training
- Fully managed, auto-scaling
- Best for production pipelines

### 8.3 Data Format

**SageMaker Input Format**: CSV
- Header: No header row
- Features: All numerical, comma-separated
- Label: Last column (0 = legitimate, 1 = fraud)
- Order: Must match `feature_extractor.py` exactly

**Example**:
```
1.5,3.0,120.0,14,2,0,0.75,1,0,0,0,0,0,0.0,1,500,0.05,0.8,0.6,1,0,0.0,1,2,0.0,0,0,0,0.3,0.5,0
```

**S3 Storage Format**:
- **Path**: `s3://{DataBucket}/fraud-detection/training/processed/`
- **Files**: `train.csv`, `val.csv`, `test.csv`
- **Encoding**: UTF-8
- **Compression**: Optional (gzip for large files)

### 8.4 Environment Variables

**Required**:
- `SAGEMAKER_ROLE` - IAM role ARN for SageMaker (from template)
- `S3_BUCKET` - S3 bucket name (from `DataBucket` output)
- `S3_PREFIX` - S3 prefix for training data (default: `fraud-detection/training`)
- `ENDPOINT_NAME` - SageMaker endpoint name (default: `fraudguard-xgboost-endpoint`)

**Optional**:
- `USE_SMOTE` - Use SMOTE for class imbalance (default: true)
- `USE_HPO` - Use hyperparameter optimization (default: true)
- `TRAINING_INSTANCE_TYPE` - SageMaker training instance (default: `ml.m5.xlarge`)
- `ENDPOINT_INSTANCE_TYPE` - Endpoint instance type (default: `ml.t2.medium`)

**Getting Values from Stack**:
```bash
# Get S3 bucket name
aws cloudformation describe-stacks \
  --stack-name fraudguard-ai-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue' \
  --output text

# Get SageMaker role ARN (after adding to template)
aws iam get-role --role-name fraudguard-ai-dev-sagemaker-role
```

---

## 9. AWS Resource Implementation Plan

### 9.1 Phase 1: Add SageMaker Resources to Template

**Add to `template.yaml`**:

1. **SageMaker Execution Role**:
   - IAM role with S3 and SageMaker permissions
   - Reference in training scripts

2. **Data Processing Lambda** (optional):
   - Process TalkingData files
   - Engineer features
   - Upload to S3

3. **SageMaker Endpoint** (uncomment and update):
   - Endpoint configuration
   - Model reference (will be created after training)
   - Auto-scaling configuration

### 9.2 Phase 2: Data Processing Workflow

**Option A: Local Processing** (Quick Start)
1. Process TalkingData locally
2. Upload processed data to S3
3. Run training script locally
4. Deploy model via script

**Option B: AWS-Native Processing** (Production)
1. Upload raw TalkingData to S3
2. Trigger Lambda or SageMaker Processing Job
3. Process data in AWS
4. Store processed data in S3
5. Trigger training job

### 9.3 Phase 3: Training Execution

**Using Existing Resources**:
- **S3 Bucket**: Use `DataBucket` from template
- **IAM Role**: Create SageMaker execution role
- **Training**: Run via SageMaker SDK (local or Lambda)
- **Storage**: Model artifacts in S3

**Training Job Configuration**:
```python
# Use DataBucket from stack
s3_bucket = get_stack_output('DataBucketName')
s3_prefix = 'fraud-detection/training'

# Use SageMaker role from stack
sagemaker_role = get_stack_output('SageMakerExecutionRoleArn')
```

### 9.4 Phase 4: Endpoint Deployment

**After Training**:
1. Model artifact stored in S3
2. Create SageMaker Model resource
3. Create Endpoint Configuration
4. Deploy Endpoint
5. Update Lambda environment variable

**Integration**:
- Update `Orchestrator` Lambda: `SAGEMAKER_ENDPOINT` environment variable
- Test endpoint invocation
- Monitor CloudWatch metrics

## 10. Risk Mitigation

### 10.1 Data Risks

**Risk**: TalkingData features don't match production features
- **Mitigation**: Create mapping layer, use defaults for missing features
- **Fallback**: Generate synthetic data with exact feature set

**Risk**: Class imbalance too extreme
- **Mitigation**: Use SMOTE or `scale_pos_weight`
- **Fallback**: Adjust sampling strategy

**Risk**: Data quality issues
- **Mitigation**: Comprehensive data validation
- **Fallback**: Clean data, remove outliers

### 10.2 Training Risks

**Risk**: Training takes too long
- **Mitigation**: Start with sample data, use efficient instances
- **Fallback**: Reduce dataset size, use faster instances

**Risk**: Model doesn't meet performance targets
- **Mitigation**: HPO, feature engineering, ensemble methods
- **Fallback**: Try alternative algorithms (LightGBM, AutoGluon)

**Risk**: Overfitting
- **Mitigation**: Cross-validation, regularization, early stopping
- **Fallback**: Reduce model complexity, increase training data

### 10.3 Deployment Risks

**Risk**: Endpoint latency too high
- **Mitigation**: Optimize instance type, use batch inference
- **Fallback**: Use smaller model, optimize features

**Risk**: Endpoint costs too high
- **Mitigation**: Use appropriate instance types, auto-scaling
- **Fallback**: Use serverless inference, batch processing

---

## 11. Success Metrics

### 11.1 Model Performance

- ✅ Cohen's Kappa > 0.75 (target: > 0.88)
- ✅ F1 Score > 0.75 (target: > 0.88)
- ✅ ROC AUC > 0.95
- ✅ Balanced Accuracy > 0.85 (target: > 0.90)

### 11.2 Operational Performance

- ✅ Inference latency < 100ms (p95)
- ✅ Endpoint availability > 99%
- ✅ Error rate < 0.1%

### 11.3 Business Impact

- ✅ Fraud detection rate improvement
- ✅ False positive rate reduction
- ✅ Cost per detection

---

## 12. Timeline

### Week 1: Data Preparation & Baseline
- Days 1-2: Feature engineering script
- Days 3-4: Data processing and validation
- Day 5: Baseline model training

### Week 2: Optimization & Deployment
- Days 1-2: Hyperparameter optimization
- Days 3-4: Model evaluation and selection
- Day 5: Model deployment and integration

### Week 3: Retraining Pipeline
- Days 1-3: Retraining automation
- Days 4-5: Testing and documentation

**Total Timeline**: 3 weeks

---

## 13. Dependencies

### 13.1 Data Dependencies

- ✅ TalkingData dataset (available)
- ⏳ FDB datasets (need Kaggle API)
- ⏳ IP reputation data (optional, for better features)
- ⏳ User agent database (optional, for bot detection)

### 13.2 Infrastructure Dependencies

- ✅ SageMaker access and IAM role
- ✅ S3 bucket for training data
- ✅ AWS credentials configured
- ⏳ SageMaker endpoint quota (if needed)

### 13.3 Software Dependencies

- ✅ Python 3.11+
- ✅ SageMaker SDK
- ✅ Pandas, NumPy, Scikit-learn
- ✅ Imbalanced-learn (for SMOTE)
- ✅ Boto3

---

## 14. Appendices

### Appendix A: Feature Mapping

**TalkingData → Production Features**:

| TalkingData | Production Feature | Notes |
|-------------|-------------------|-------|
| `ip` | IP address (for aggregation) | Compute `ip_click_count_24h` |
| `device` | Device ID | Compute `device_click_count_1h` |
| `click_time` | Timestamp | Extract `hour_of_day`, `day_of_week` |
| `os` | Device OS | Encode to `device_os_encoded` |
| `app` | App ID | Can map to campaign-like features |
| `channel` | Channel ID | Can map to publisher-like features |
| `is_attributed` | Label | Invert to `is_fraud` |

**Missing Features** (need defaults or external data):
- User agent features (not in TalkingData)
- IP reputation (need external service)
- Referrer (not in TalkingData)
- Click-to-view time (not in TalkingData)

### Appendix B: Sample Training Command

```bash
# Set environment variables
export SAGEMAKER_ROLE="arn:aws:iam::123456789012:role/SageMakerExecutionRole"
export S3_BUCKET="fraudguard-training-data"
export S3_PREFIX="fraud-detection/training"
export ENDPOINT_NAME="fraudguard-xgboost-endpoint"

# Run training
python3 scripts/train_xgboost_sagemaker.py
```

### Appendix C: CloudFormation Template Additions

**File**: `template-sagemaker-additions.yaml`

This file contains the CloudFormation resources to add to `template.yaml`:

1. **SageMaker Execution Role** - IAM role for SageMaker operations
2. **Data Processing Lambda** - Process training data (optional)
3. **SageMaker Endpoint Resources** - Model, endpoint config, endpoint

**To Add**:
1. Copy resources from `template-sagemaker-additions.yaml`
2. Insert into `template.yaml` after API Gateway section (around line 322)
3. Add conditions and parameters as specified in the file
4. Deploy updated stack: `sam build && sam deploy`

### Appendix D: AWS Resource Quick Reference

**Existing Resources** (from current stack):
- **S3 Bucket**: `{StackName}-data-{AccountId}` (DataBucket)
- **DynamoDB Table**: `fraudguard-events-{Environment}`
- **Lambda Functions**: Multiple (ingestion, orchestrator, ai-analyzer, etc.)

**New Resources** (to be added):
- **SageMaker Execution Role**: `{StackName}-sagemaker-execution-role`
- **Data Processing Lambda**: `{StackName}-data-processing` (optional)
- **SageMaker Endpoint**: `{StackName}-xgboost-endpoint` (after training)

**S3 Paths**:
- Raw data: `s3://{bucket}/fraud-detection/training/raw/`
- Processed data: `s3://{bucket}/fraud-detection/training/processed/`
- Models: `s3://{bucket}/fraud-detection/models/xgboost/`

**Getting Resource Names**:
```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name fraudguard-ai-dev \
  --query 'Stacks[0].Outputs'

# Get S3 bucket name
aws cloudformation describe-stacks \
  --stack-name fraudguard-ai-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DataBucketName`].OutputValue' \
  --output text
```

### Appendix E: References

- [XGBoost Training Guide](./XGBOOST_TRAINING_GUIDE.md)
- [AWS Blog: Fraud Detection](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/)
- [TalkingData Dataset Analysis](./TALKINGDATA_DATASET_ANALYSIS.md)
- [Training Data Inventory](./TRAINING_DATA_INVENTORY.md)
- [SageMaker XGBoost Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [SageMaker Built-in Algorithms](https://docs.aws.amazon.com/sagemaker/latest/dg/algos.html)

---

## Document Control

**Version History**:
- v1.0 (Nov 2024) - Initial PRD

**Reviewers**:
- ML Engineering Team
- Data Science Team
- DevOps Team

**Approval**:
- [ ] Technical Lead
- [ ] Product Manager
- [ ] Engineering Manager

