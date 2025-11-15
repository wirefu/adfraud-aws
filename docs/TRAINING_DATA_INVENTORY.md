# Training Data Inventory

## Current Status: ⚠️ **No Actual Training Data Files Yet**

While we've set up infrastructure to download and use training data, **no actual training data files have been downloaded yet**.

## Available Data Sources

### 1. ✅ **FDB (Fraud Dataset Benchmark)** - Framework Downloaded

**Status**: Framework/code downloaded, but **actual datasets need to be downloaded via Kaggle API**

**Location**: `data/fdb/fraud-dataset-benchmark-main/`

**What's Available**:
- ✅ Python package for loading datasets
- ✅ Configuration files for 9 different fraud datasets
- ✅ Training scripts and examples

**What's Missing**:
- ❌ Actual dataset files (need Kaggle API to download)
- ❌ Labeled training samples

**Datasets Available via FDB** (once downloaded):
1. **IEEE-CIS Fraud Detection** - 561,013 train samples (3.50% fraud)
2. **Credit Card Fraud Detection** - 227,845 train samples (0.18% fraud)
3. **Fraud ecommerce** - 120,889 train samples (10.60% fraud)
4. **Simulated Credit Card Transactions (Sparkov)** - 1,296,675 train samples (5.70% fraud)
5. **Twitter Bot Accounts** - 29,950 train samples (33.10% fraud)
6. **Malicious URLs** - 586,072 train samples (34.20% fraud)
7. **Fake Job Posting Prediction** - 14,304 train samples (4.70% fraud)
8. **Vehicle Loan Default Prediction** - 186,523 train samples (21.60% fraud)
9. **IP Blocklist** - 172,000 train samples (7% fraud)

**To Download**: Requires Kaggle API setup and joining competitions

### 2. ⏳ **TalkingData AdTracking Fraud Detection** - Ready to Download

**Status**: Script ready, but **not downloaded yet** (requires joining Kaggle competition)

**Location**: Will be in `data/talkingdata/` after download

**Dataset Details**:
- **Size**: Millions of records (200k+ labeled samples)
- **Features**: IP address, App ID, Device ID, OS version, Channel ID, Click timestamp
- **Label**: Is attributed (fraud label)
- **Relevance**: ⭐⭐⭐⭐⭐ **Highly relevant** - Mobile ad clicks with fraud labels

**To Download**:
1. Join competition: https://www.kaggle.com/competitions/talkingdata-adtracking-fraud-detection
2. Run: `python3 scripts/download_talkingdata_kaggle.py`

### 3. ⏳ **Historical Google Ads Data** - Script Available

**Status**: Import script exists, but **data not imported yet**

**Location**: Would be in DynamoDB after import

**Script**: `scripts/import_historical_google_ads_data.py`

**Data Details**:
- **Source**: Google Ads API
- **Date Range**: Nov 2023 to Nov 2024 (shifted forward by 1 year)
- **Includes**: Campaign performance, keywords, placements, click details
- **Issue**: ⚠️ **Not labeled** - Needs fraud labels for training

**To Import**:
```bash
python3 scripts/import_historical_google_ads_data.py
```

**Note**: This data needs to be labeled (fraud/legitimate) before it can be used for training.

### 4. 📝 **Synthetic Data Generation** - Code Example Available

**Status**: Code example in PRD, but **not generated yet**

**Location**: Would be in `data/synthetic/` after generation

**Code**: Example in `docs/ad-fraud-detection-prd.md` (lines 2135-2182)

**Details**:
- **Size**: Can generate 100k+ samples
- **Class Balance**: 70% legitimate, 30% fraud (configurable)
- **Patterns**: Bot traffic, click farms, device farms

**To Generate**: Implement the PRD example code or create a script

## Summary: What You Have vs What You Need

### ✅ **What You Have**:
1. ✅ Download scripts for TalkingData
2. ✅ FDB framework (code, not data)
3. ✅ Import script for Google Ads data
4. ✅ Synthetic data generation example
5. ✅ Training pipeline documentation

### ❌ **What You're Missing**:
1. ❌ **Actual labeled training data files**
2. ❌ **TalkingData dataset** (need to join competition and download)
3. ❌ **FDB datasets** (need Kaggle API to download)
4. ❌ **Labeled Google Ads data** (data exists but needs labels)
5. ❌ **Synthetic data** (code exists but not generated)

## Recommended Next Steps

### Priority 1: Get TalkingData Dataset ⭐⭐⭐⭐⭐

**Why**: Most relevant to your ad fraud use case

**Steps**:
1. Join Kaggle competition: https://www.kaggle.com/competitions/talkingdata-adtracking-fraud-detection
2. Run: `python3 scripts/download_talkingdata_kaggle.py`
3. Verify: Check `data/talkingdata/` for CSV files

**Expected Result**: Millions of labeled ad click records

### Priority 2: Generate Synthetic Data ⭐⭐⭐⭐

**Why**: Quick way to get 100k+ labeled samples for initial training

**Steps**:
1. Create script based on PRD example
2. Generate 100k samples (70% legit, 30% fraud)
3. Save to `data/synthetic/training_data.csv`

**Expected Result**: 100,000 labeled samples ready for training

### Priority 3: Download FDB Datasets ⭐⭐⭐

**Why**: Additional diverse fraud datasets for training

**Steps**:
1. Set up Kaggle API (if not already done)
2. Join required competitions (especially IEEE-CIS)
3. Use FDB Python package to download datasets
4. Combine with other data sources

**Expected Result**: 9 additional fraud datasets

### Priority 4: Label Google Ads Data ⭐⭐

**Why**: Your own domain-specific data

**Steps**:
1. Import historical data: `python3 scripts/import_historical_google_ads_data.py`
2. Create labeling process (manual or rule-based)
3. Label events as fraud/legitimate
4. Export labeled data for training

**Expected Result**: Domain-specific labeled training data

## Minimum Requirements for Training

According to your PRD:
- **Minimum**: 100,000 labeled samples
- **Class Balance**: 70% legitimate, 30% fraud
- **Split**: 70% train, 15% validation, 15% test

**Current Status**: ❌ **0 labeled samples available**

## Quick Start: Get Training Data Now

### Option 1: Synthetic Data (Fastest) ⚡

```python
# Create scripts/generate_synthetic_data.py
# Based on PRD example (lines 2135-2182)
# Generate 100k samples
# Takes ~5-10 minutes
```

### Option 2: TalkingData (Most Relevant) 🎯

```bash
# 1. Join competition (5 minutes)
# 2. Download (30-60 minutes depending on size)
python3 scripts/download_talkingdata_kaggle.py
```

### Option 3: FDB Datasets (Most Diverse) 📊

```python
# Use FDB Python package
from fdb.datasets import FraudDatasetBenchmark

# Download datasets via Kaggle API
obj = FraudDatasetBenchmark(key='ccfraud')
train_data = obj.train
```

## Data Format Requirements

Your training data must match your feature extractor:

**Required Features** (from `src/orchestrator/feature_extractor.py`):
1. `ip_click_count_24h`
2. `device_click_count_1h`
3. `time_since_last_click`
4. `hour_of_day`
5. `day_of_week`
6. `ua_is_bot`
7. `ua_entropy`
8. `ip_is_datacenter`
9. `ip_is_vpn`
10. ... (20+ total features)

**Label**: `is_fraud` (0 = legitimate, 1 = fraud)

**Note**: Downloaded datasets may need feature engineering to match your extractor.

## Next Actions

1. ⏳ **Download TalkingData** - Most relevant, ready to download
2. ⏳ **Generate synthetic data** - Quick way to get started
3. ⏳ **Download FDB datasets** - Additional training data
4. ⏳ **Label Google Ads data** - Domain-specific data

**Current Status**: Ready to download/generate, but no actual data files yet.

