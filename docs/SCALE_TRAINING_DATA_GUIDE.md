# Scale Training Data Guide

## Overview

This guide walks through scaling the training data from 10,000 records to larger datasets (100k, 500k, 1M+) to improve model performance.

**Current Status**: Model trained on 10,000 records (F1: 0.9975, ROC AUC: 0.7447)  
**Goal**: Process larger dataset and retrain to potentially improve performance

---

## Step 1: Choose Dataset Size

### Recommended Incremental Approach

Start with smaller increments to validate the pipeline:

1. **100k records** (~15 minutes processing)
   - Good for initial validation
   - Quick to process and train
   - Compare with 10k baseline

2. **500k records** (~1 hour processing)
   - Significant increase
   - Better representation of data distribution
   - Recommended for production

3. **1M+ records** (~2-4 hours processing)
   - Maximum benefit
   - Best model performance
   - Use if 500k shows improvement

### Dataset Availability

**TalkingData Dataset**:
- Full dataset: `data/talkingdata/train.csv` (7.0 GB, ~185M records)
- Sample: `data/talkingdata/train_sample.csv` (3.9 MB, ~100k records)

**Current Training Data**: 10,000 records

---

## Step 2: Process Scaled Dataset

### Option A: Process 100k Records (Recommended First Step)

```bash
python3 scripts/scale_training_data.py \
    --nrows 100000 \
    --compress
```

**Expected Output**:
- Training: ~70,000 samples
- Validation: ~15,000 samples
- Test: ~15,000 samples
- Processing time: ~15-20 minutes

### Option B: Process 500k Records (Production Scale)

```bash
python3 scripts/scale_training_data.py \
    --nrows 500000 \
    --use-smote \
    --compress
```

**Expected Output**:
- Training: ~350,000 samples
- Validation: ~75,000 samples
- Test: ~75,000 samples
- Processing time: ~1-1.5 hours

### Option C: Process 1M Records (Maximum Scale)

```bash
python3 scripts/scale_training_data.py \
    --nrows 1000000 \
    --use-smote \
    --compress
```

**Expected Output**:
- Training: ~700,000 samples
- Validation: ~150,000 samples
- Test: ~150,000 samples
- Processing time: ~2-3 hours

---

## Step 3: Verify Processed Data

After processing, verify the data quality:

```bash
# Check S3 location
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/scaled-100k-*/

# Or use the verification notebook
jupyter lab notebooks/verify_processed_training_data.ipynb
```

**Checks**:
- ✅ Feature count: 29 features
- ✅ No missing values
- ✅ No infinite values
- ✅ Class distribution reasonable
- ✅ Data types correct

---

## Step 4: Train Model with Scaled Data

### Update Training Script

The training script will automatically use the latest processed data from S3, or you can specify the path:

```bash
# Train with 100k dataset
python3 scripts/hpo_xgboost_sagemaker.py \
    --train-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/scaled-100k-YYYYMMDD-HHMMSS/train.csv.gz \
    --val-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/scaled-100k-YYYYMMDD-HHMMSS/val.csv.gz
```

### Compare Performance

After training, compare metrics:

| Dataset Size | F1 Score | ROC AUC | Training Time | Notes |
|--------------|----------|---------|---------------|-------|
| 10k (baseline) | 0.9975 | 0.7447 | ~5 min | Current model |
| 100k | TBD | TBD | ~15 min | First scale |
| 500k | TBD | TBD | ~45 min | Production |
| 1M+ | TBD | TBD | ~2 hours | Maximum |

---

## Step 5: Deploy Improved Model

If the scaled dataset shows improved performance:

1. **Evaluate on test set**:
   ```bash
   python3 scripts/evaluate_model.py \
       --test-s3-path s3://.../test.csv.gz \
       --endpoint-name fraudguard-xgboost-endpoint
   ```

2. **Deploy new model** (if better):
   ```bash
   python3 scripts/fix_endpoint_deployment.py \
       --endpoint-name fraudguard-xgboost-endpoint \
       --model-s3-path s3://.../model.tar.gz
   ```

3. **Monitor performance** in production

---

## Processing Options

### With SMOTE (Recommended for Imbalanced Data)

SMOTE helps balance the dataset by oversampling minority class:

```bash
python3 scripts/scale_training_data.py \
    --nrows 500000 \
    --use-smote \
    --compress
```

**Benefits**:
- Better class balance
- Improved model performance on minority class
- Reduces overfitting to majority class

**Trade-offs**:
- Longer processing time
- Larger output files
- May slightly overfit to synthetic samples

### Compression

Always use compression for large datasets:

```bash
--compress  # Default: enabled
```

**Benefits**:
- Smaller file sizes (50-70% reduction)
- Faster S3 upload/download
- Lower storage costs

---

## Cost Estimates

### Processing Costs

| Dataset Size | Processing Time | SageMaker Processing Cost* |
|--------------|-----------------|----------------------------|
| 100k | ~15 min | ~$0.10 |
| 500k | ~1 hour | ~$0.40 |
| 1M | ~2-3 hours | ~$0.80-1.20 |

*Using `ml.m5.xlarge` instance

### Storage Costs

| Dataset Size | Uncompressed | Compressed | Monthly Cost* |
|--------------|--------------|------------|---------------|
| 100k | ~50 MB | ~15 MB | <$0.01 |
| 500k | ~250 MB | ~75 MB | <$0.01 |
| 1M | ~500 MB | ~150 MB | <$0.01 |

*S3 Standard storage

---

## Troubleshooting

### Out of Memory

If processing fails with memory errors:

1. **Reduce batch size** in processing script
2. **Process in smaller chunks** (already enabled with `use_chunking=True`)
3. **Use larger instance** for SageMaker processing job

### Slow Processing

If processing is too slow:

1. **Check instance type** (use `ml.m5.xlarge` or larger)
2. **Disable SMOTE** for initial runs
3. **Process smaller subset first** (100k before 1M)

### Data Quality Issues

If verification fails:

1. **Check feature engineering** logic
2. **Verify input data** format
3. **Review preprocessing** steps
4. **Check for data corruption** in source file

---

## Recommended Workflow

### Phase 1: Validation (Week 1)

1. Process 100k records
2. Train and evaluate
3. Compare with 10k baseline
4. Document findings

### Phase 2: Production Scale (Week 2)

1. If 100k shows improvement, process 500k
2. Train and evaluate
3. Deploy if significantly better
4. Monitor in production

### Phase 3: Maximum Scale (Month 2)

1. If needed, process 1M+ records
2. Train and evaluate
3. A/B test against current model
4. Deploy if better

---

## Success Metrics

Track these when scaling:

1. **Model Performance**:
   - F1 Score (target: maintain or improve)
   - ROC AUC (target: > 0.75)
   - False positive rate (target: < 5%)

2. **Training Efficiency**:
   - Training time per 100k records
   - Cost per training run
   - Convergence speed

3. **Production Impact**:
   - Fraud detection rate
   - False positive reduction
   - Cost savings

---

## Summary

**Quick Start**:
```bash
# 1. Process 100k records
python3 scripts/scale_training_data.py --nrows 100000 --compress

# 2. Train model
python3 scripts/hpo_xgboost_sagemaker.py

# 3. Evaluate
python3 scripts/evaluate_model.py

# 4. Compare with baseline
```

**Expected Timeline**:
- 100k processing: ~15 minutes
- Training: ~15 minutes
- Evaluation: ~5 minutes
- **Total: ~35 minutes**

---

## References

- **Processing Script**: `scripts/scale_training_data.py`
- **Training Guide**: `docs/BOT_TRAFFIC_TRAINING_GUIDE.md`
- **Data Processing**: `docs/DATA_PROCESSING_WALKTHROUGH.md`
- **Roadmap**: `docs/NEXT_STEPS_ROADMAP.md` (Step 4)

