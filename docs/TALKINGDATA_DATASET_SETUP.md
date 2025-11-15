# TalkingData AdTracking Fraud Detection Dataset Setup

## Overview

The **TalkingData AdTracking Fraud Detection** dataset from Kaggle is highly relevant for training your ad fraud detection models. This dataset contains millions of mobile app ad clicks with fraud labels.

**Kaggle Competition**: https://www.kaggle.com/competitions/talkingdata-adtracking-fraud-detection

## Dataset Details

- **Size**: Millions of records (200k+ labeled samples mentioned in PRD)
- **Features**: 
  - IP address
  - App ID
  - Device ID
  - OS version
  - Channel ID
  - Click timestamp
  - Is attributed (fraud label)
- **Use Case**: Train XGBoost fraud detection model, feature engineering, benchmarking

## Setup Instructions

### Step 1: Join the Kaggle Competition

**IMPORTANT**: You must join the competition on Kaggle before downloading:

1. Visit: https://www.kaggle.com/competitions/talkingdata-adtracking-fraud-detection
2. Click **"Join Competition"** button
3. Accept the competition rules and terms
4. Wait a few minutes for the system to process your join request

### Step 2: Verify Kaggle Credentials

Your Kaggle credentials are already configured at `~/.kaggle/kaggle.json`. If you get a 401 error:

1. Go to https://www.kaggle.com/settings
2. Scroll to "API" section
3. Click "Create New API Token" (or "Expire" and recreate if needed)
4. Download the new `kaggle.json`
5. Replace `~/.kaggle/kaggle.json` with the new file
6. Set permissions: `chmod 600 ~/.kaggle/kaggle.json`

### Step 3: Download the Dataset

Once you've joined the competition, run:

```bash
python3 scripts/download_talkingdata_kaggle.py
```

The script will:
- ✅ Check Kaggle API availability
- ✅ Verify credentials
- ✅ Download competition files
- ✅ Extract zip files automatically
- ✅ Create dataset metadata

**Output Location**: `data/talkingdata/`

## Integration with Training Pipeline

### For XGBoost Model Training

This dataset can be used to:

1. **Train the XGBoost model** - Provides the required 100,000+ labeled samples
2. **Feature engineering** - Extract patterns relevant to ad fraud
3. **Validation** - Use as a benchmark dataset

### Combining with Other Datasets

You now have access to multiple training data sources:

1. **TalkingData** (this dataset) - Mobile ad clicks with fraud labels
2. **FDB Datasets** - 9 different fraud detection datasets (already downloaded)
3. **Historical Google Ads Data** - Your own data from `scripts/import_historical_google_ads_data.py`
4. **Synthetic Data** - Can be generated using the PRD example code

### Example Usage

After downloading, you can integrate it into your training pipeline:

```python
import pandas as pd
from pathlib import Path

# Load TalkingData dataset
talkingdata_path = Path("data/talkingdata")
train_df = pd.read_csv(talkingdata_path / "train.csv")

# Combine with other datasets if needed
# Process and prepare for XGBoost training
```

## Troubleshooting

### Error: 401 Unauthorized
- **Solution**: Check Kaggle credentials and ensure you've joined the competition

### Error: 403 Forbidden
- **Solution**: Make sure you've clicked "Join Competition" and accepted the rules

### Error: Competition not found
- **Solution**: Verify the competition URL is correct and accessible

### Download is slow
- **Normal**: The dataset is large (several GB). Be patient.
- The script shows progress during download

## Next Steps

1. ✅ Join the competition on Kaggle
2. ✅ Run the download script
3. ✅ Review downloaded files
4. ✅ Integrate into training pipeline
5. ✅ Use for XGBoost model training

## Related Files

- **Download Script**: `scripts/download_talkingdata_kaggle.py`
- **FDB Datasets**: `data/fdb/` (already downloaded)
- **Training Notebook**: `scripts/train_xgboost_notebook.ipynb`
- **PRD Reference**: `docs/ad-fraud-detection-prd.md` (line 2127-2129)

