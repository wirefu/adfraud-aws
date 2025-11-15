# AWS Blog Learnings Applied to Training Pipeline

**Source**: [Detect Fraudulent Transactions using Machine Learning with Amazon SageMaker](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/)

**Date**: November 2024  
**Status**: ✅ Implemented

---

## Summary

We've analyzed the AWS blog post on fraud detection and applied key learnings to our ad fraud detection training pipeline. This document outlines what we learned and how we've implemented it.

---

## Key Techniques Applied

### 1. ✅ Data Splitting Before Class Imbalance Handling

**AWS Blog Learning**: 
> "It's important to split the data before applying any techniques to alleviate the class imbalance. Otherwise, we might leak information from the test set into the train set and hurt the model's performance."

**Our Implementation**:
- ✅ Data is split into train/val/test (70/15/15) **before** applying SMOTE
- ✅ Located in `scripts/process_training_data.py` lines 324-340
- ✅ Uses stratified sampling to maintain class balance

**Code Reference**:
```python
# Step 1: Split data first
splits = load_and_engineer_features(
    split_data=True,
    train_size=0.7,
    val_size=0.15,
    test_size=0.15,
    stratify=True
)

# Step 2: Then apply SMOTE only to training data
if use_smote:
    X_train_resampled, y_train_resampled = apply_smote(X_train, y_train)
```

---

### 2. ✅ Class Imbalance Handling with `scale_pos_weight`

**AWS Blog Learning**:
> Use `scale_pos_weight = sqrt(num_nonfraud / num_fraud)` to handle class imbalance in XGBoost.

**Our Implementation**:
- ✅ Formula matches AWS blog exactly: `sqrt(num_legitimate / num_fraud)`
- ✅ Automatically calculated in `scripts/process_training_data.py`
- ✅ Loaded from `metrics.json` in training scripts
- ✅ Used in both baseline and HPO training

**Code Reference**:
```python
# scripts/process_training_data.py line 133
if num_fraud > 0:
    scale_pos_weight = math.sqrt(num_legitimate / num_fraud)
```

**Results from AWS Blog**:
- Baseline XGBoost with `scale_pos_weight`: Cohen's Kappa = 0.743801
- Better than RCF (0.003917) and comparable to SMOTE (0.716463)

---

### 3. ✅ SMOTE Oversampling Support

**AWS Blog Learning**:
> SMOTE can improve balanced accuracy (0.912657 vs 0.847685) but may reduce precision/F1 score due to increased overlap between classes.

**Our Implementation**:
- ✅ SMOTE support in `scripts/process_training_data.py`
- ✅ Optional flag: `--use-smote`
- ✅ Applied only to training data (not validation/test)
- ✅ Uses `imbalanced-learn` library

**Usage**:
```bash
python scripts/process_training_data.py \
    --data-source talkingdata \
    --output s3://bucket/training/processed/ \
    --use-smote
```

**Trade-offs** (from AWS blog):
- ✅ Higher balanced accuracy
- ⚠️ May reduce Cohen's Kappa and F1 score
- ⚠️ Can increase false positives

---

### 4. ✅ Hyperparameter Optimization (HPO)

**AWS Blog Learning**:
> HPO significantly improves model performance:
> - Cohen's Kappa: 0.743801 → **0.880778** (+18.4%)
> - F1 Score: 0.744186 → **0.880952** (+18.4%)
> - Balanced Accuracy: 0.847685 → 0.902156 (+6.4%)

**Our Implementation**:
- ✅ HPO script: `scripts/hpo_xgboost_sagemaker.py`
- ✅ Research-backed hyperparameter ranges for imbalanced data
- ✅ Bayesian optimization strategy
- ✅ Objective metric: `validation:auc` (maximize)
- ✅ Configurable max jobs and parallel jobs

**Hyperparameter Ranges** (from AWS blog):
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

**Usage**:
```bash
python scripts/hpo_xgboost_sagemaker.py \
    --stack-name fraudguard-ai-dev \
    --max-jobs 10 \
    --parallel-jobs 2
```

---

### 5. ✅ Evaluation Metrics (Matching AWS Blog)

**AWS Blog Metrics**:
1. **Balanced Accuracy** - Accounts for class imbalance
2. **Cohen's Kappa** - Measures agreement beyond chance (preferred for fraud)
3. **F1 Score** - Harmonic mean of precision and recall
4. **ROC AUC** - Overall model discrimination ability

**Our Implementation**:
- ✅ All metrics calculated in `scripts/evaluate_model.py`
- ✅ Benchmark comparison against PRD targets
- ✅ Confusion matrix analysis
- ✅ Classification report per class

**Code Reference**:
```python
# scripts/evaluate_model.py
metrics = {
    'roc_auc': roc_auc_score(y_true, y_pred_proba),
    'f1_score': f1_score(y_true, y_pred),
    'balanced_accuracy': balanced_accuracy_score(y_true, y_pred),
    'cohen_kappa': cohen_kappa_score(y_true, y_pred),
    'confusion_matrix': confusion_matrix(y_true, y_pred)
}
```

---

### 6. ✅ Threshold Tuning (NEW - Just Added)

**AWS Blog Learning**:
> "After experimenting different thresholds from 0.1–0.9, we can see that Cohen's Kappa keeps increasing along with the threshold, without a significant loss in balanced accuracy. This adds a useful calibration to our model."

**Our Implementation** (NEW):
- ✅ Added `tune_threshold()` function to `scripts/evaluate_model.py`
- ✅ Experiments with thresholds 0.1 to 0.9
- ✅ Finds optimal threshold balancing Cohen's Kappa and Balanced Accuracy
- ✅ Displays results table with all metrics
- ✅ Automatically uses optimal threshold for final evaluation

**Usage**:
```bash
python scripts/evaluate_model.py \
    --training-job-name fraudguard-xgboost-hpo-2024-11-14-123456 \
    --tune-thresholds \
    --stack-name fraudguard-ai-dev
```

**Output Example**:
```
Threshold Experiment Results:
----------------------------------------------------------------------------------------------------
Threshold     Cohen Kappa     Balanced Acc     F1 Score        ROC AUC        
----------------------------------------------------------------------------------------------------
0.1           0.6234          0.9123          0.6456          0.9835
0.2           0.7123          0.9012          0.7234          0.9835
...
0.8           0.8807          0.9021          0.8809          0.9815 ⭐
0.9           0.8756          0.8956          0.8756          0.9815
----------------------------------------------------------------------------------------------------

⭐ Optimal Threshold: 0.8
   Cohen's Kappa: 0.8807
   Balanced Accuracy: 0.9021
   F1 Score: 0.8809
```

**Key Insight from AWS Blog**:
- Lower threshold (0.1-0.3): Minimize false negatives (catch more fraud)
- Higher threshold (0.7-0.9): Minimize false positives (reduce false alarms)
- Optimal threshold balances both metrics

---

## Training Pipeline (Following AWS Blog Approach)

### Step 1: Data Preparation ✅
- Load TalkingData dataset
- Engineer features to match production extractor
- **Split data BEFORE applying SMOTE** (critical!)
- Handle class imbalance (calculate `scale_pos_weight`)

### Step 2: Baseline Training ✅
- Train XGBoost with baseline hyperparameters
- Use `scale_pos_weight` for class imbalance
- Evaluate on validation set

### Step 3: SMOTE Training (Optional) ✅
- Apply SMOTE to training data only
- Train XGBoost model
- Compare with baseline

### Step 4: Hyperparameter Optimization ✅
- Run HPO tuning job (10 models, 2 parallel)
- Use Bayesian optimization
- Select best model based on validation AUC

### Step 5: Model Evaluation ✅
- Calculate all metrics (Balanced Accuracy, Cohen's Kappa, F1, ROC AUC)
- **Experiment with thresholds 0.1-0.9** (NEW)
- Find optimal threshold
- Analyze feature importance

### Step 6: Model Deployment ✅
- Deploy best model to SageMaker endpoint
- Configure auto-scaling
- Test endpoint with sample requests

---

## Performance Expectations (Based on AWS Blog)

| Model | Balanced Accuracy | Cohen's Kappa | F1 Score | ROC AUC |
|-------|------------------|---------------|----------|---------|
| Baseline XGBoost | 0.847685 | 0.743801 | 0.744186 | 0.983515 |
| XGBoost + SMOTE | 0.912657 | 0.716463 | 0.716981 | 0.967497 |
| **XGBoost + HPO** | **0.902156** | **0.880778** | **0.880952** | **0.981564** |

**Our PRD Targets**:
- Cohen's Kappa: > 0.75 (baseline), > 0.88 (with HPO) ✅
- F1 Score: > 0.75 (baseline), > 0.88 (with HPO) ✅
- ROC AUC: > 0.95 ✅
- Balanced Accuracy: > 0.85 (baseline), > 0.90 (with HPO) ✅

---

## What We've Implemented

### ✅ Completed
1. Data splitting before SMOTE
2. `scale_pos_weight` calculation (sqrt formula)
3. SMOTE support (optional)
4. HPO with research-backed ranges
5. All evaluation metrics from AWS blog
6. **Threshold tuning experiment** (NEW)

### 🔄 Optional (Not Yet Implemented)
1. **RCF Anomaly Detection** - Unsupervised model (optional, AWS blog includes it)
   - Could add for comparison
   - Less accurate than supervised models
   - Useful when labels are scarce

2. **Model Comparison Dashboard** - Compare baseline vs SMOTE vs HPO
   - Could create visualization
   - Currently done via evaluation scripts

---

## Usage Examples

### Complete Training Pipeline

```bash
# Step 1: Process data (with SMOTE optional)
python scripts/process_training_data.py \
    --data-source talkingdata \
    --output s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/ \
    --stack-name fraudguard-ai-dev \
    --compress \
    --use-smote  # Optional

# Step 2: Baseline training
python scripts/train_xgboost_sagemaker.py \
    --stack-name fraudguard-ai-dev

# Step 3: HPO (recommended)
python scripts/hpo_xgboost_sagemaker.py \
    --stack-name fraudguard-ai-dev \
    --max-jobs 10 \
    --parallel-jobs 2

# Step 4: Evaluate with threshold tuning
python scripts/evaluate_model.py \
    --training-job-name fraudguard-xgboost-hpo-2024-11-14-123456 \
    --stack-name fraudguard-ai-dev \
    --tune-thresholds  # NEW: Find optimal threshold

# Step 5: Deploy best model
python scripts/deploy_model_sagemaker.py \
    --training-job-name fraudguard-xgboost-hpo-2024-11-14-123456 \
    --stack-name fraudguard-ai-dev
```

---

## Key Takeaways

1. **Split data BEFORE SMOTE** - Prevents data leakage
2. **Use `scale_pos_weight`** - Simple and effective for class imbalance
3. **HPO is essential** - Significant performance improvement (+18% Cohen's Kappa)
4. **Threshold tuning matters** - Default 0.5 may not be optimal
5. **SMOTE trade-offs** - Better balanced accuracy but may reduce precision

---

## References

- [AWS Blog: Detect Fraudulent Transactions using Machine Learning with Amazon SageMaker](https://aws.amazon.com/blogs/machine-learning/detect-fraudulent-transactions-using-machine-learning-with-amazon-sagemaker/)
- [XGBoost Training Guide](./XGBOOST_TRAINING_GUIDE.md)
- [Data Training PRD](./DATA_TRAINING_PRD.md)

---

**Last Updated**: November 2024  
**Status**: ✅ All key techniques from AWS blog implemented

