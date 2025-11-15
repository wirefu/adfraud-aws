# Process Sample Data for Training

A focused script for quickly processing sample training data for testing and development.

## Overview

The `scripts/process_sample_data.py` script is designed for:
- **Quick testing** - Process small sample datasets rapidly
- **Development** - Generate synthetic data when real data isn't available
- **Prototyping** - Test training pipelines with minimal data

## Features

- ✅ Generate synthetic sample data (if no real data available)
- ✅ Process TalkingData sample files
- ✅ Process synthetic data files
- ✅ Feature engineering (matches production feature extractor)
- ✅ Train/validation/test splitting
- ✅ SMOTE oversampling (optional)
- ✅ Format for SageMaker XGBoost
- ✅ Save locally or upload to S3
- ✅ Gzip compression (optional)

## Quick Start

### Option 1: Generate and Process Synthetic Data (Recommended for Testing)

This is the fastest way to get started when you don't have real data files:

```bash
# Generate 10,000 synthetic samples and process them
python scripts/process_sample_data.py \
    --generate-synthetic \
    --nrows 10000 \
    --output ./processed_sample/
```

This will:
1. Generate 10,000 synthetic samples (30% fraud, 70% legitimate)
2. Engineer features matching production
3. Split into train/val/test (70/15/15)
4. Save formatted files to `./processed_sample/`

### Option 2: Process TalkingData Sample

If you have the TalkingData sample file downloaded:

```bash
python scripts/process_sample_data.py \
    --data-source talkingdata \
    --output ./processed_sample/
```

### Option 3: With SMOTE and Compression

For better class balance and smaller file sizes:

```bash
python scripts/process_sample_data.py \
    --generate-synthetic \
    --nrows 10000 \
    --use-smote \
    --compress \
    --output ./processed_sample/
```

## Output Files

The script generates:

- `train.csv` (or `train.csv.gz`) - Training data in SageMaker format
- `val.csv` (or `val.csv.gz`) - Validation data
- `test.csv` (or `test.csv.gz`) - Test data
- `metrics.json` - Class distribution and scale_pos_weight metrics

## SageMaker Format

All CSV files are formatted for SageMaker XGBoost:
- **No header row**
- **Features in exact order** matching production feature extractor
- **Label as last column** (0 = legitimate, 1 = fraud)
- **All numerical values**, comma-separated

## Command-Line Options

```bash
--data-source {talkingdata,synthetic}
    Data source to use (default: talkingdata)

--output OUTPUT
    Output directory or S3 URI (default: ./processed_sample/)

--nrows NROWS
    Limit number of rows to process (for testing)

--generate-synthetic
    Generate synthetic sample data first

--use-smote
    Apply SMOTE oversampling to handle class imbalance

--compress
    Compress output files with gzip

--train-size TRAIN_SIZE
    Training set proportion (default: 0.7)

--val-size VAL_SIZE
    Validation set proportion (default: 0.15)

--test-size TEST_SIZE
    Test set proportion (default: 0.15)

--random-state RANDOM_STATE
    Random seed for reproducibility (default: 42)
```

## Examples

### Generate 5,000 samples for quick testing

```bash
python scripts/process_sample_data.py \
    --generate-synthetic \
    --nrows 5000 \
    --output ./test_data/
```

### Process with custom split ratios

```bash
python scripts/process_sample_data.py \
    --generate-synthetic \
    --nrows 10000 \
    --train-size 0.8 \
    --val-size 0.1 \
    --test-size 0.1 \
    --output ./processed_sample/
```

### Upload directly to S3

```bash
python scripts/process_sample_data.py \
    --generate-synthetic \
    --nrows 10000 \
    --output s3://your-bucket/training/processed/
```

## Synthetic Data Generation

When using `--generate-synthetic`, the script generates realistic fraud patterns:

- **Bot traffic** - Datacenter IPs, limited devices, old OS versions
- **Click farms** - Same IP ranges, limited device diversity
- **Device farms** - Very limited devices, suspicious patterns
- **Datacenter traffic** - Private IP ranges, server-like patterns

The synthetic data mimics TalkingData format:
- IP address (integer encoded)
- App ID
- Device ID
- OS version
- Channel ID
- Click timestamp
- Attribution status (label)

## Integration with Training Pipeline

The processed files can be used directly with:

1. **SageMaker XGBoost Training** - Use the CSV files directly
2. **Local XGBoost Training** - Load CSV files with pandas
3. **Model Evaluation** - Use test set for validation

Example usage in training:

```python
import pandas as pd

# Load processed training data
train_df = pd.read_csv('processed_sample/train.csv', header=None)
# Features are in columns 0 to N-1, label is in column N
```

## Differences from Full Processing Script

This script (`process_sample_data.py`) is focused on **sample data**:
- ✅ Smaller datasets (typically 1k-50k samples)
- ✅ Faster processing
- ✅ Synthetic data generation built-in
- ✅ Simplified options

The full script (`process_training_data.py`) handles:
- ✅ Large datasets (millions of rows)
- ✅ Chunked processing
- ✅ Multiple data sources (FDB, Google Ads, etc.)
- ✅ More advanced options

## Troubleshooting

### Error: "TalkingData file not found"

**Solution**: Use `--generate-synthetic` to create sample data, or download TalkingData first:
```bash
python scripts/download_talkingdata_kaggle.py
```

### Error: "imbalanced-learn is required for SMOTE"

**Solution**: Install the package:
```bash
pip install imbalanced-learn
```

### Error: "Feature engineering failed"

**Solution**: Ensure all dependencies are installed:
```bash
pip install -r scripts/requirements.txt
pip install -r training/requirements.txt
```

## Next Steps

After processing sample data:

1. **Review metrics.json** - Check class distribution and scale_pos_weight
2. **Test training** - Use processed files with XGBoost
3. **Scale up** - Use `process_training_data.py` for full datasets
4. **Deploy** - Use processed data for SageMaker training jobs

## Related Files

- **Full Processing Script**: `scripts/process_training_data.py`
- **Feature Engineering**: `training/feature_engineering.py`
- **Data Loader**: `training/data_loader.py`
- **Training Guide**: `docs/XGBOOST_TRAINING_GUIDE.md`

