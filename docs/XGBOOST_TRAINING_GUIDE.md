# XGBoost Training Guide

Based on AWS Best Practices: [Detect Fraudulent Transactions using Machine Learning with Amazon SageMaker](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/)

## Overview

This guide explains how to train your XGBoost fraud detection model using SageMaker, following AWS best practices for handling class imbalance and optimizing model performance.

## Key Techniques from AWS Blog

### 1. **Class Imbalance Handling**

The AWS blog demonstrates two approaches:

#### A. XGBoost Built-in Weighting (`scale_pos_weight`)
- Formula: `sqrt(num_nonfraud / num_fraud)`
- Automatically adjusts for imbalanced classes
- No data preprocessing needed

#### B. SMOTE (Synthetic Minority Over-sampling Technique)
- Generates synthetic fraud samples
- Balances the dataset before training
- Can improve balanced accuracy but may reduce precision

**Recommendation**: Start with `scale_pos_weight`, then try SMOTE if needed.

### 2. **Hyperparameter Optimization (HPO)**

The blog shows that HPO significantly improves performance:

| Metric | Baseline XGBoost | XGBoost with HPO |
|--------|------------------|------------------|
| Balanced Accuracy | 0.847685 | 0.902156 |
| Cohen's Kappa | 0.743801 | **0.880778** |
| F1 Score | 0.744186 | **0.880952** |
| ROC AUC | 0.983515 | 0.981564 |

### 3. **Evaluation Metrics**

Use these metrics (as shown in AWS blog):
- **Balanced Accuracy**: Accounts for class imbalance
- **Cohen's Kappa**: Measures agreement beyond chance
- **F1 Score**: Harmonic mean of precision and recall
- **ROC AUC**: Overall model discrimination ability

### 4. **Threshold Tuning**

After training, experiment with classification thresholds (0.1-0.9):
- Lower threshold (0.1-0.3): Minimize false negatives (catch more fraud)
- Higher threshold (0.7-0.9): Minimize false positives (reduce false alarms)

## Training Pipeline

### Prerequisites

1. **AWS Credentials**: Configure AWS CLI with appropriate permissions
2. **SageMaker Role**: IAM role with SageMaker permissions
3. **S3 Bucket**: For storing training data and model artifacts
4. **Training Data**: At least 100,000 labeled samples

### Step 1: Prepare Training Data

Your training script should:
1. Load data from multiple sources:
   - TalkingData dataset (`data/talkingdata/`)
   - FDB datasets (`data/fdb/`)
   - Historical Google Ads data

2. Extract features matching your `feature_extractor.py`:
   - 20+ features as defined in your codebase
   - Ensure feature order matches training data

3. Split data: 70% train, 15% validation, 15% test

### Step 2: Handle Class Imbalance

```python
# Calculate scale_pos_weight
num_fraud = y_train.sum()
num_nonfraud = len(y_train) - num_fraud
scale_pos_weight = np.sqrt(num_nonfraud / num_fraud)

# Or apply SMOTE
from imblearn.over_sampling import SMOTE
smote = SMOTE(random_state=42)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
```

### Step 3: Train with SageMaker XGBoost

```python
from sagemaker.xgboost.estimator import XGBoost

xgb_estimator = XGBoost(
    role=sagemaker_role,
    instance_type='ml.m5.xlarge',
    framework_version='1.7-1',
    hyperparameters={
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'scale_pos_weight': scale_pos_weight,
        'num_round': 100,
    }
)

xgb_estimator.fit({
    'train': TrainingInput(s3_train_path, content_type='text/csv'),
    'validation': TrainingInput(s3_val_path, content_type='text/csv'),
})
```

### Step 4: Hyperparameter Optimization (Optional but Recommended)

```python
from sagemaker.tuner import HyperparameterTuner, IntegerParameter, ContinuousParameter

hyperparameter_ranges = {
    'num_round': IntegerParameter(50, 200),
    'max_depth': IntegerParameter(3, 10),
    'eta': ContinuousParameter(0.01, 0.3),
    'gamma': ContinuousParameter(0, 5),
    'min_child_weight': IntegerParameter(1, 10),
    'subsample': ContinuousParameter(0.5, 1.0),
    'colsample_bytree': ContinuousParameter(0.5, 1.0),
}

tuner = HyperparameterTuner(
    estimator=xgb_estimator,
    objective_metric_name='validation:auc',
    objective_type='Maximize',
    hyperparameter_ranges=hyperparameter_ranges,
    max_jobs=10,
    max_parallel_jobs=2,
)

tuner.fit({
    'train': TrainingInput(s3_train_path, content_type='text/csv'),
    'validation': TrainingInput(s3_val_path, content_type='text/csv'),
})
```

### Step 5: Deploy Model

```python
predictor = tuner.best_estimator().deploy(
    initial_instance_count=1,
    instance_type='ml.t2.medium',  # Use ml.m5.large for production
    endpoint_name='fraudguard-xgboost-endpoint',
    serializer=sagemaker.serializers.CSVSerializer(),
    deserializer=sagemaker.deserializers.CSVDeserializer()
)
```

### Step 6: Evaluate Model

```python
from sklearn.metrics import balanced_accuracy_score, cohen_kappa_score, f1_score, roc_auc_score

# Get predictions
predictions = []
for row in X_test.iterrows():
    response = predictor.predict(','.join(map(str, row[1].values)))
    predictions.append(float(response.decode('utf-8').strip()))

# Calculate metrics
y_pred = (np.array(predictions) >= 0.5).astype(int)
metrics = {
    'balanced_accuracy': balanced_accuracy_score(y_test, y_pred),
    'cohen_kappa': cohen_kappa_score(y_test, y_pred),
    'f1': f1_score(y_test, y_pred),
    'roc_auc': roc_auc_score(y_test, predictions),
}
```

## Integration with Your Codebase

### Update Environment Variables

After deploying, update your Lambda environment:

```yaml
# In template.yaml
Environment:
  Variables:
    SAGEMAKER_ENDPOINT: fraudguard-xgboost-endpoint
```

### Feature Alignment

Ensure your training data features match `src/orchestrator/feature_extractor.py`:

The extractor returns features in this order:
1. `ip_click_count_24h`
2. `device_click_count_1h`
3. `time_since_last_click`
4. `hour_of_day`
5. `day_of_week`
6. `ua_is_bot`
7. `ua_entropy`
8. `ip_is_datacenter`
9. `ip_is_vpn`
10. `ip_is_proxy`
11. `ip_is_business`
12. `ip_is_competitor`
13. `geo_distance_km`
14. `referrer_is_valid`
15. `click_to_view_time_ms`
16. `campaign_fraud_rate`
17. `publisher_quality`
18. `device_fingerprint_entropy`
19. `is_mobile`
20. `is_repeated_click`
21. `time_to_conversion_sec`
22. `ip_country_encoded`
23. `device_os_encoded`
24. ... (additional features)

**Important**: Your training data must have features in the exact same order!

## Expected Performance

Based on AWS blog results, you should aim for:

- **Balanced Accuracy**: > 0.85
- **Cohen's Kappa**: > 0.75 (with HPO: > 0.88)
- **F1 Score**: > 0.75 (with HPO: > 0.88)
- **ROC AUC**: > 0.95

## Cost Considerations

- **Training**: 
  - `ml.m5.xlarge`: ~$0.23/hour
  - HPO with 10 jobs: ~$2.30 (if sequential) or ~$4.60 (if 2 parallel)
- **Endpoint**:
  - `ml.t2.medium`: ~$0.065/hour (~$47/month)
  - `ml.m5.large`: ~$0.115/hour (~$83/month)

## Next Steps

1. ✅ Download training datasets (TalkingData, FDB)
2. ✅ Create training script based on AWS blog approach
3. ⏳ Prepare and format training data
4. ⏳ Train baseline XGBoost model
5. ⏳ Run HPO for optimal model
6. ⏳ Deploy to SageMaker endpoint
7. ⏳ Update Lambda environment variables
8. ⏳ Test end-to-end fraud detection

## References

- [AWS Blog: Fraud Detection with SageMaker](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/)
- [SageMaker XGBoost Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [SageMaker Hyperparameter Tuning](https://docs.aws.amazon.com/sagemaker/latest/dg/automatic-model-tuning.html)

