# AWS Blog Learnings: Fraud Detection with SageMaker

## Summary

I've analyzed the AWS blog post on [fraud detection using SageMaker](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/) and extracted key learnings applicable to your ad fraud detection project.

## Key Techniques Implemented

### 1. Class Imbalance Handling

**Problem**: Fraud detection datasets are highly imbalanced (often <1% fraud rate)

**Solutions from AWS Blog**:

#### A. XGBoost `scale_pos_weight` Parameter
- Formula: `sqrt(num_nonfraud / num_fraud)`
- Automatically weights fraud class during training
- No data preprocessing required
- **Result**: Improved Cohen's Kappa from baseline

#### B. SMOTE (Synthetic Minority Over-sampling)
- Generates synthetic fraud samples
- Balances dataset before training
- **Result**: Higher balanced accuracy (0.912657 vs 0.847685)
- **Trade-off**: May reduce precision/F1 score

**Your Implementation**: Both methods are now documented in the training guide

### 2. Hyperparameter Optimization (HPO)

**Key Finding**: HPO significantly improves model performance

| Metric | Baseline | With HPO | Improvement |
|--------|----------|----------|-------------|
| Cohen's Kappa | 0.743801 | **0.880778** | +18.4% |
| F1 Score | 0.744186 | **0.880952** | +18.4% |
| Balanced Accuracy | 0.847685 | 0.902156 | +6.4% |

**Hyperparameter Ranges** (from AWS blog):
- `num_round`: 50-200
- `max_depth`: 3-10
- `eta`: 0.01-0.3
- `gamma`: 0-5
- `min_child_weight`: 1-10
- `subsample`: 0.5-1.0
- `colsample_bytree`: 0.5-1.0

**Your Implementation**: HPO configuration included in training guide

### 3. Evaluation Metrics

**AWS Blog Uses**:
1. **Balanced Accuracy**: Accounts for class imbalance
2. **Cohen's Kappa**: Measures agreement beyond chance (preferred for fraud)
3. **F1 Score**: Harmonic mean of precision/recall
4. **ROC AUC**: Overall discrimination ability

**Why These Matter**:
- Standard accuracy is misleading with imbalanced data
- Cohen's Kappa is particularly important for fraud detection
- F1 balances precision and recall

**Your Implementation**: All metrics included in evaluation function

### 4. Threshold Tuning

**Key Insight**: Default 0.5 threshold may not be optimal

**AWS Blog Approach**:
- Experiment with thresholds 0.1-0.9
- Lower threshold (0.1-0.3): Catch more fraud (minimize false negatives)
- Higher threshold (0.7-0.9): Reduce false alarms (minimize false positives)

**Your Current Thresholds**:
- Fraud: > 0.8 (block immediately)
- Legitimate: < 0.3 (allow immediately)
- Borderline: 0.3-0.8 (route to AI)

**Recommendation**: After training, experiment with threshold tuning

## Architecture Alignment

### What Matches Your Project

✅ **XGBoost Algorithm**: You're already using XGBoost  
✅ **SageMaker Deployment**: Your code expects SageMaker endpoint  
✅ **Class Imbalance**: Your PRD mentions 70% legitimate, 30% fraud  
✅ **Binary Classification**: Fraud vs legitimate  
✅ **Real-time Inference**: Your orchestrator calls SageMaker endpoint  

### What's Different

🔄 **Dataset**: AWS blog uses credit card transactions, you use ad clicks  
🔄 **Features**: Different feature set (20+ features for ad fraud)  
🔄 **Two-Tier System**: You have ML + AI ensemble, blog focuses on ML only  

## Implementation Status

### ✅ Completed

1. **Training Guide Created**: `docs/XGBOOST_TRAINING_GUIDE.md`
   - Step-by-step instructions
   - Code examples from AWS blog
   - Integration with your codebase

2. **Requirements Updated**: `scripts/sagemaker_training_requirements.txt`
   - Added `imbalanced-learn` for SMOTE

3. **Documentation**: This summary document

### ⏳ Next Steps

1. **Create Training Script**: Full Python script implementing AWS blog approach
2. **Prepare Training Data**: Format datasets to match your feature extractor
3. **Train Baseline Model**: Start with `scale_pos_weight` approach
4. **Run HPO**: Optimize hyperparameters for best performance
5. **Deploy Endpoint**: Create SageMaker endpoint
6. **Update Lambda**: Point orchestrator to new endpoint

## Code Examples from AWS Blog

### Training with Class Weighting

```python
scale_pos_weight = np.sqrt(num_nonfraud / num_fraud)

xgb_estimator = XGBoost(
    hyperparameters={
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'scale_pos_weight': scale_pos_weight,
    }
)
```

### Training with SMOTE

```python
from imblearn.over_sampling import SMOTE

smote = SMOTE(random_state=42)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
```

### Hyperparameter Optimization

```python
tuner = HyperparameterTuner(
    estimator=xgb_estimator,
    objective_metric_name='validation:auc',
    objective_type='Maximize',
    hyperparameter_ranges={
        'num_round': IntegerParameter(50, 200),
        'max_depth': IntegerParameter(3, 10),
        # ... more ranges
    },
    max_jobs=10,
    max_parallel_jobs=2,
)
```

## Performance Expectations

Based on AWS blog results, with proper training you should achieve:

- **Balanced Accuracy**: > 0.85 (target: > 0.90 with HPO)
- **Cohen's Kappa**: > 0.75 (target: > 0.88 with HPO)
- **F1 Score**: > 0.75 (target: > 0.88 with HPO)
- **ROC AUC**: > 0.95

## Cost Considerations

**Training** (one-time):
- Baseline: ~$0.23/hour × 1 hour = $0.23
- HPO (10 jobs, 2 parallel): ~$2.30-4.60

**Endpoint** (ongoing):
- `ml.t2.medium`: ~$47/month (dev/staging)
- `ml.m5.large`: ~$83/month (production)

## References

- [AWS Blog Post](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/)
- [SageMaker XGBoost Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [Training Guide](./XGBOOST_TRAINING_GUIDE.md)

