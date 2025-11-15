# TalkingData Dataset Analysis

## ✅ Dataset Successfully Extracted

**Location**: `data/talkingdata/`

**Files Extracted**:
- `train.csv` - **7.0 GB** - Main training dataset
- `train_sample.csv` - **3.9 MB** - Sample for quick testing
- `test.csv` - **823 MB** - Test dataset
- `test_supplement.csv` - **2.5 GB** - Additional test data
- `sample_submission.csv` - **187 MB** - Submission format

## Dataset Overview

### Training Data

**File**: `train.csv` (7.0 GB)
- **Size**: Very large dataset (likely millions of rows)
- **Use**: Primary training data for XGBoost model

**File**: `train_sample.csv` (3.9 MB)
- **Size**: Smaller sample for quick testing
- **Use**: Good for initial model development and testing

### Test Data

**File**: `test.csv` (823 MB)
- **Size**: Large test set
- **Use**: Final model evaluation

**File**: `test_supplement.csv` (2.5 GB)
- **Size**: Additional test data
- **Use**: Extended evaluation

## Expected Schema

Based on Kaggle competition description, the dataset should contain:

**Features**:
- `ip` - IP address
- `app` - App ID
- `device` - Device ID
- `os` - Operating system version
- `channel` - Channel ID
- `click_time` - Timestamp of click
- `attributed_time` - Timestamp of attribution (if attributed)

**Label**:
- `is_attributed` - Binary label (0 = not attributed/fraud, 1 = attributed/legitimate)
  - **Note**: This is inverted from typical fraud labels
  - `is_attributed = 0` means fraud (click didn't lead to install)
  - `is_attributed = 1` means legitimate (click led to install)

## Data Size

**Total Dataset Size**: ~11.3 GB (uncompressed)

**Training Data**: 
- Full: `train.csv` (7.0 GB) - Millions of records
- Sample: `train_sample.csv` (3.9 MB) - Smaller subset for testing

## Next Steps

### 1. Inspect Data Structure

```python
import pandas as pd

# Load sample first to understand structure
df_sample = pd.read_csv('data/talkingdata/train_sample.csv')
print(df_sample.head())
print(df_sample.info())
print(df_sample.describe())
```

### 2. Map to Your Feature Extractor

The TalkingData features need to be mapped to your `feature_extractor.py` requirements:

**TalkingData Features** → **Your Features**:
- `ip` → IP address (for IP-based features)
- `device` → Device ID (for device-based features)
- `os` → Device OS
- `click_time` → Timestamp (for temporal features)
- `app` → App ID (can be used for campaign-like features)
- `channel` → Channel ID (can be used for publisher-like features)

**Missing Features** (need to compute):
- `ip_click_count_24h` - Need to aggregate by IP
- `device_click_count_1h` - Need to aggregate by device
- `time_since_last_click` - Need to compute from click_time
- `ua_is_bot` - Not available (no user agent)
- `ip_is_datacenter` - Need IP reputation lookup
- `ip_is_vpn` - Need IP reputation lookup
- ... (other features from your extractor)

### 3. Feature Engineering Required

You'll need to create a feature engineering script that:

1. **Loads TalkingData**:
   ```python
   df = pd.read_csv('data/talkingdata/train.csv', nrows=100000)  # Start with subset
   ```

2. **Computes Aggregated Features**:
   - IP click counts (24h window)
   - Device click counts (1h window)
   - Time since last click
   - Temporal features (hour_of_day, day_of_week)

3. **Adds IP Reputation** (if available):
   - Datacenter detection
   - VPN detection
   - Proxy detection

4. **Maps Label**:
   ```python
   # Invert label: is_attributed=0 means fraud
   df['is_fraud'] = 1 - df['is_attributed']
   ```

5. **Outputs in Your Feature Format**:
   - Match the exact feature order from `feature_extractor.py`
   - Save as CSV for SageMaker training

### 4. Training Data Preparation

**Recommended Approach**:

1. **Start with Sample**: Use `train_sample.csv` for initial development
2. **Feature Engineering**: Create script to compute all 20+ features
3. **Full Dataset**: Once working, process full `train.csv` (may need chunking)
4. **Split Data**: 70% train, 15% validation, 15% test
5. **Upload to S3**: For SageMaker training

## Dataset Statistics

**File Sizes**:
- `train.csv`: 7.0 GB (main training data)
- `train_sample.csv`: 3.9 MB (quick testing)
- `test.csv`: 823 MB
- `test_supplement.csv`: 2.5 GB

**Estimated Records** (based on typical CSV sizes):
- `train.csv`: Likely 100+ million records
- `train_sample.csv`: Likely 100k-1M records

## Integration with Training Pipeline

### Quick Start (Using Sample)

```python
# Load sample data
df = pd.read_csv('data/talkingdata/train_sample.csv')

# Feature engineering
# ... (implement feature extraction)

# Prepare for training
# ... (match your feature extractor format)

# Save for SageMaker
df.to_csv('data/talkingdata/train_processed.csv', index=False)
```

### Full Dataset (Production)

```python
# Process in chunks (7GB is too large for memory)
chunk_size = 100000
for chunk in pd.read_csv('data/talkingdata/train.csv', chunksize=chunk_size):
    # Feature engineering
    # ... (process each chunk)
    
    # Append to output file
    # ...
```

## Label Mapping

**Important**: TalkingData uses `is_attributed` which is inverted from typical fraud labels:

- `is_attributed = 0` → **Fraud** (click didn't lead to install)
- `is_attributed = 1` → **Legitimate** (click led to install)

**For Training**:
```python
df['is_fraud'] = 1 - df['is_attributed']
# Now: is_fraud = 1 means fraud, is_fraud = 0 means legitimate
```

## Summary

✅ **Dataset Available**: TalkingData successfully extracted  
✅ **Size**: 7.0 GB training data (millions of records)  
✅ **Sample Available**: 3.9 MB sample for quick testing  
⏳ **Next Step**: Create feature engineering script to map to your feature extractor

This dataset provides **more than enough** training data (well above your 100k minimum requirement)!

