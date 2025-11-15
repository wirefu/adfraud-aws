# Google Ads Data Preparation Guide

## Overview

This guide explains how to prepare Google Ads data for training, including train/test splitting to reserve data for testing.

## Quick Start

### Basic Usage (with train/test split)

```bash
# Prepare data with 70/30 train/test split (default)
python3 training/prepare_google_ads_training_data.py \
    --soft-labels \
    --test-size 0.3 \
    --output data/training/google_ads_prepared.csv
```

This will create:
- `data/training/google_ads_prepared_train.csv` - Training data (70%)
- `data/training/google_ads_prepared_test.csv` - Test data (30%)

### Recommended Command (with all features)

```bash
# Prepare with soft labels, relabeling, and train/test split
python3 training/prepare_google_ads_training_data.py \
    --soft-labels \
    --relabel \
    --test-size 0.3 \
    --output data/training/google_ads_prepared.csv \
    --suspicious 50
```

## Command Options

### Label Types

- `--soft-labels` (default): Use fraud scores as soft labels (0.0-1.0) with sample weights
- `--hard-labels`: Use binary labels (0 or 1) only

### Train/Test Splitting

- `--test-size FLOAT`: Proportion for testing (default: 0.3 = 30%)
  - Use `0.0` to skip splitting (returns all data as training)
- `--stratify` (default): Use stratified sampling to maintain class balance
- `--no-stratify`: Disable stratified sampling (use random split)
- `--temporal-split`: Split by timestamp (older = train, newer = test)
- `--random-state INT`: Random seed for reproducibility (default: 42)

### Data Enhancement

- `--relabel`: Apply rule-based relabeling for suspicious cases
- `--suspicious N`: Identify top N suspicious cases for manual review

## Split Strategies

### 1. Stratified Split (Recommended) ⭐⭐⭐⭐⭐

**Best for**: Maintaining class balance in both train and test sets

```bash
python3 training/prepare_google_ads_training_data.py \
    --soft-labels \
    --test-size 0.3 \
    --output data/training/google_ads_prepared.csv
```

**Result**:
- Training: ~6,744 items (15 fraud cases)
- Test: ~2,891 items (7 fraud cases)
- Maintains ~0.22% fraud rate in both sets

### 2. Temporal Split ⭐⭐⭐⭐

**Best for**: Testing on newer data (simulates real-world scenario)

```bash
python3 training/prepare_google_ads_training_data.py \
    --soft-labels \
    --test-size 0.3 \
    --temporal-split \
    --output data/training/google_ads_prepared.csv
```

**Result**:
- Training: Older 70% of data
- Test: Newer 30% of data
- Better simulates production deployment

### 3. Custom Split Ratio

```bash
# Use 20% for testing (more training data)
python3 training/prepare_google_ads_training_data.py \
    --soft-labels \
    --test-size 0.2 \
    --output data/training/google_ads_prepared.csv
```

## Expected Results

### With Soft Labels (Recommended)

**Training Set** (~6,744 items):
- High confidence fraud (label > 0.5): ~15-18 items
- Suspicious (0.3 < label <= 0.5): ~15-20 items
- Legitimate (label <= 0.3): ~6,706 items

**Test Set** (~2,891 items):
- High confidence fraud (label > 0.5): ~6-7 items
- Suspicious (0.3 < label <= 0.5): ~6-8 items
- Legitimate (label <= 0.3): ~2,876 items

### With Hard Labels

**Training Set**:
- Fraud: ~15 items (0.22%)
- Legitimate: ~6,729 items (99.78%)

**Test Set**:
- Fraud: ~7 items (0.24%)
- Legitimate: ~2,884 items (99.76%)

## Using the Prepared Data

### For XGBoost Training

```python
import pandas as pd
import xgboost as xgb

# Load prepared data
train_df = pd.read_csv('data/training/google_ads_prepared_train.csv')
test_df = pd.read_csv('data/training/google_ads_prepared_test.csv')

# Extract features and labels
X_train = train_df[feature_columns]
y_train = train_df['fraud_label']
sample_weight_train = train_df['sample_weight']

X_test = test_df[feature_columns]
y_test = test_df['fraud_label']
sample_weight_test = test_df['sample_weight']

# Train model
model = xgb.XGBClassifier()
model.fit(
    X_train,
    y_train,
    sample_weight=sample_weight_train,
    eval_set=[(X_test, y_test)],
    eval_sample_weight=[sample_weight_test]
)
```

### For Combined Training (TalkingData + Google Ads)

```python
# Load TalkingData (primary training)
talkingdata_train = load_talkingdata_training()

# Load Google Ads (domain-specific)
google_ads_train = pd.read_csv('data/training/google_ads_prepared_train.csv')
google_ads_test = pd.read_csv('data/training/google_ads_prepared_test.csv')

# Train on TalkingData first
model.fit(X_talkingdata, y_talkingdata)

# Fine-tune on Google Ads
model.fit(
    google_ads_train[feature_columns],
    google_ads_train['fraud_label'],
    sample_weight=google_ads_train['sample_weight'],
    xgb_model=model.get_booster()  # Continue training
)

# Evaluate on Google Ads test set
test_predictions = model.predict(google_ads_test[feature_columns])
```

## Best Practices

1. **Always use stratified split** (default) to maintain class balance
2. **Use soft labels** for better learning signal with imbalanced data
3. **Reserve test set** - Don't use test data for training or validation
4. **Use consistent random_state** (42) for reproducibility
5. **Consider temporal split** if you want to test on newer data

## Troubleshooting

### "Too few fraud cases for stratification"

If you see this warning, the script will fall back to random split. This is fine, but be aware that class balance may not be maintained.

### "Stratified split failed"

This can happen if there's only 1 fraud case. The script will automatically fall back to random split.

### Test set has very few fraud cases

With only 22 fraud cases total, the test set will have ~6-7 fraud cases. This is expected but limits evaluation. Consider:
- Using a smaller test size (0.2 instead of 0.3)
- Using soft labels for better evaluation
- Combining with TalkingData test set for more comprehensive evaluation

## Output Files

The script creates:
- `{output}_train.csv` - Training data
- `{output}_test.csv` - Test data
- `suspicious_cases.csv` - If `--suspicious` flag is used

Each file contains:
- All original columns from DynamoDB
- `fraud_label` - Soft or hard fraud label
- `sample_weight` - Sample weight for training
- `relabeled` - Boolean indicating if item was relabeled (if `--relabel` used)

