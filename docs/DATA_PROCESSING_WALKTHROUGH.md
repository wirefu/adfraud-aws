# Data Processing Walkthrough

Complete step-by-step guide to how raw training data is processed into SageMaker-ready format.

---

## Overview

**Pipeline**: Raw TalkingData CSV → Feature Engineering → Preprocessing → Data Splitting → SageMaker Format → S3 Upload

**Key Scripts**:
- `scripts/process_training_data_sagemaker.py` - Main processing script (runs in SageMaker Processing Job)
- `training/feature_engineering.py` - Feature engineering logic
- `training/preprocessing.py` - Data preprocessing
- `training/data_splitting.py` - Train/val/test splitting

---

## Step-by-Step Process

### Step 1: Load Raw Data from S3

**Location**: `scripts/process_training_data_sagemaker.py` (lines 44-90)

**What Happens**:
1. Downloads raw CSV file from S3 (e.g., `s3://bucket/fraud-detection/training/raw/train.csv`)
2. Loads into pandas DataFrame
3. For TalkingData, expects columns: `ip`, `app`, `device`, `os`, `channel`, `click_time`, `is_attributed`

**Input Format** (TalkingData):
```csv
ip,app,device,os,channel,click_time,is_attributed
123456,12,1,13,497,2017-11-06 14:32:21,0
789012,12,1,13,497,2017-11-06 14:33:45,1
...
```

**Code**:
```python
def load_data_from_s3(s3_path: str, data_source: str, nrows: Optional[int] = None):
    # Download from S3
    s3_client.download_file(bucket, file_key, local_file)
    # Load CSV
    df = pd.read_csv(local_file, nrows=nrows)
    return df
```

---

### Step 2: Label Conversion

**Location**: `training/feature_engineering.py` (lines 370-372)

**What Happens**:
- Converts TalkingData's `is_attributed` label to `is_fraud` label
- `is_attributed = 0` → `is_fraud = 1` (fraud - click didn't lead to attribution)
- `is_attributed = 1` → `is_fraud = 0` (legitimate - click led to attribution)

**Code**:
```python
# Convert label: is_attributed=0 means fraud, is_attributed=1 means legitimate
if 'is_attributed' in df.columns:
    df['is_fraud'] = 1 - df['is_attributed']
```

**Result**:
- DataFrame now has `is_fraud` column (0 or 1)

---

### Step 3: Feature Engineering

**Location**: `training/feature_engineering.py` - `engineer_talkingdata_features()`

**What Happens**:
Transforms raw TalkingData columns into 29 features matching your production feature extractor.

#### 3.1: Aggregated Features (Time-Based)

**Location**: `training/feature_engineering.py` - `compute_aggregated_features()`

**Features Created**:
1. **`ip_click_count_24h`**: Number of clicks from same IP in last 24 hours
2. **`device_click_count_1h`**: Number of clicks from same device in last 1 hour
3. **`time_since_last_click`**: Seconds since previous click from same device

**How It Works**:
- Groups data by IP/device
- For each row, counts previous rows within time window
- Uses vectorized operations for efficiency

**Code Example**:
```python
# For each IP, count clicks in 24h window
ip_groups = df.groupby('ip')
for ip, ip_group in ip_groups:
    for i in range(len(ip_group)):
        current_time = ip_group.iloc[i]['click_time']
        window_start = current_time - timedelta(hours=24)
        # Count previous clicks within window
        count = sum(1 for t in prev_times if window_start <= t < current_time)
        ip_group.iloc[i]['ip_click_count_24h'] = count
```

#### 3.2: Temporal Features

**Features Created**:
4. **`hour_of_day`**: Hour of day (0-23) from `click_time`
5. **`day_of_week`**: Day of week (0=Monday, 6=Sunday) from `click_time`

**Code**:
```python
df['hour_of_day'] = df['click_time'].dt.hour
df['day_of_week'] = df['click_time'].dt.dayofweek
```

#### 3.3: IP Address Features

**Features Created**:
6. **`ip_is_datacenter`**: Check if IP is datacenter (using IP reputation)
7. **`ip_is_vpn`**: Check if IP is VPN
8. **`ip_is_proxy`**: Check if IP is proxy
9. **`ip_is_business`**: Check if IP is business
10. **`ip_is_competitor`**: Check if IP is competitor
11. **`ip_country_encoded`**: Encoded country code

**How It Works**:
- Converts integer IP to string format
- Queries IP reputation services (or uses cached data)
- Sets binary flags (0 or 1)

#### 3.4: User Agent Features

**Features Created**:
12. **`ua_is_bot`**: Detects bot signatures in user agent (0 or 1)
13. **`ua_entropy`**: Measures user agent complexity (0.0-1.0)

**Note**: TalkingData doesn't have user agent data, so these are set to defaults (0 for bot, 0.5 for entropy)

#### 3.5: Device Features

**Features Created**:
14. **`device_os_encoded`**: Encoded OS ID
15. **`is_mobile`**: Mobile device flag (0 or 1)
16. **`device_fingerprint_entropy`**: Device fingerprint complexity

#### 3.6: Campaign & Publisher Features

**Features Created**:
17. **`campaign_fraud_rate`**: Historical fraud rate for campaign/channel
18. **`publisher_quality`**: Publisher quality score (0.0-1.0)

**How It Works**:
- Aggregates historical fraud rates by channel/campaign
- Uses rolling averages or lookup tables

#### 3.7: Engagement Features

**Features Created**:
19. **`referrer_is_valid`**: Valid referrer flag (0 or 1)
20. **`click_to_view_time_ms`**: Time from click to view (milliseconds)
21. **`is_repeated_click`**: Repeated click flag (0 or 1)
22. **`time_to_conversion_sec`**: Time to conversion (seconds)
23. **`click_to_install_time_sec`**: Time to install (seconds)
24. **`has_recent_install`**: Recent install flag (0 or 1)
25. **`install_broadcast_detected`**: Install broadcast detection (0 or 1)
26. **`conversion_rate`**: Conversion rate
27. **`engagement_score`**: Overall engagement score (0.0-1.0)

#### 3.8: Geographic Features

**Features Created**:
28. **`geo_distance_km`**: Geographic distance (kilometers)

#### 3.9: Risk Score Features

**Features Created**:
29. **`click_injection_risk_score`**: Click injection risk (0.0-1.0)

**Result**: DataFrame with 29 feature columns + `is_fraud` label

---

### Step 4: Preprocessing

**Location**: `training/preprocessing.py`

**What Happens**:

#### 4.1: Handle Missing Values

**Strategies**:
- **Numeric features**: Fill with 0.0 or median
- **Categorical features**: Fill with mode or "unknown"
- **Auto strategy**: Uses feature type to determine best approach

**Code**:
```python
# Fill missing numeric values with 0
df[numeric_cols] = df[numeric_cols].fillna(0.0)
# Fill missing categorical with mode
df[categorical_cols] = df[categorical_cols].fillna(df[categorical_cols].mode()[0])
```

#### 4.2: Encode Categorical Features

**What Happens**:
- Encodes categorical features (like `ip_country_encoded`, `device_os_encoded`) to numeric
- Uses label encoding or one-hot encoding

#### 4.3: Validate Data

**Checks**:
- All features are numeric
- No infinite values
- No null values
- Feature count matches expected (29)

**Result**: Clean DataFrame with all numeric features, no missing values

---

### Step 5: Data Splitting

**Location**: `training/data_splitting.py`

**What Happens**:
1. Splits data into train/validation/test sets
2. Default split: 70% train, 15% validation, 15% test
3. Uses stratified sampling to maintain class distribution

**Code**:
```python
from sklearn.model_selection import train_test_split

# First split: train vs (val + test)
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y,
    test_size=0.3,
    stratify=y,  # Maintain class distribution
    random_state=42
)

# Second split: val vs test
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp,
    test_size=0.5,  # 50% of 30% = 15%
    stratify=y_temp,
    random_state=42
)
```

**Result**: Three DataFrames: `train_df`, `val_df`, `test_df`

---

### Step 6: Calculate Class Imbalance Metrics

**Location**: `scripts/process_training_data.py` (lines 109-159)

**What Happens**:
1. Counts fraud vs legitimate samples in training set
2. Calculates `scale_pos_weight` for XGBoost
3. Formula: `scale_pos_weight = sqrt(num_nonfraud / num_fraud)`

**Code**:
```python
def calculate_class_imbalance_metrics(df, label_column='is_fraud'):
    num_fraud = df[label_column].sum()
    num_legitimate = len(df) - num_fraud
    fraud_rate = num_fraud / len(df)
    
    # AWS best practice formula
    scale_pos_weight = math.sqrt(num_legitimate / num_fraud)
    
    return {
        'num_fraud': num_fraud,
        'num_legitimate': num_legitimate,
        'fraud_rate': fraud_rate,
        'scale_pos_weight': scale_pos_weight
    }
```

**Result**: Metrics dictionary with class distribution and `scale_pos_weight`

**Example Output** (from your data):
```json
{
  "num_fraud": 6980,
  "num_legitimate": 20,
  "fraud_rate": 0.9971,
  "scale_pos_weight": 0.0535
}
```

---

### Step 7: Optional SMOTE Oversampling

**Location**: `scripts/process_training_data.py` (lines 160-195)

**What Happens** (if `--use-smote` flag is used):
1. Uses SMOTE (Synthetic Minority Over-sampling Technique) to balance classes
2. Generates synthetic fraud samples
3. Balances training set to 50/50 fraud/legitimate

**Code**:
```python
from imblearn.over_sampling import SMOTE

smote = SMOTE(random_state=42)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
```

**Result**: Balanced training set (if SMOTE used)

**Note**: Your current data was processed **without SMOTE**, so it remains imbalanced (99.71% fraud)

---

### Step 8: Format for SageMaker

**Location**: `scripts/process_training_data.py` (lines 38-106)

**What Happens**:
1. Selects features in **exact order** matching production `feature_extractor.py`
2. Ensures all 29 features are present (fills missing with 0.0)
3. Validates all values are numeric
4. Handles infinite/NaN values (replaces with 0.0)
5. Adds label as **last column**
6. Removes header row

**SageMaker Format Requirements**:
- ✅ **No header row**
- ✅ **Features in exact order** (must match `FEATURE_NAMES`)
- ✅ **Label as last column** (0 = legitimate, 1 = fraud)
- ✅ **All numeric values**
- ✅ **Comma-separated**

**Code**:
```python
def format_for_sagemaker(df, label_column='is_fraud'):
    # Select features in correct order
    feature_df = df[FEATURE_NAMES].copy()
    
    # Handle missing/infinite values
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
    feature_df = feature_df.fillna(0.0)
    
    # Convert to float
    for col in feature_df.columns:
        feature_df[col] = feature_df[col].astype(float)
    
    # Add label as last column
    label_series = df[label_column].astype(int)
    sagemaker_df = pd.concat([feature_df, label_series], axis=1)
    
    return sagemaker_df
```

**Feature Order** (must match exactly):
```python
FEATURE_NAMES = [
    'ip_click_count_24h',      # 0
    'device_click_count_1h',   # 1
    'time_since_last_click',    # 2
    'hour_of_day',              # 3
    'day_of_week',              # 4
    'ua_is_bot',                # 5
    'ua_entropy',               # 6
    'ip_is_datacenter',         # 7
    'ip_is_vpn',                # 8
    'ip_is_proxy',              # 9
    'ip_is_business',           # 10
    'ip_is_competitor',         # 11
    'geo_distance_km',          # 12
    'referrer_is_valid',        # 13
    'click_to_view_time_ms',    # 14
    'campaign_fraud_rate',      # 15
    'publisher_quality',        # 16
    'device_fingerprint_entropy', # 17
    'is_mobile',                # 18
    'is_repeated_click',        # 19
    'time_to_conversion_sec',    # 20
    'ip_country_encoded',       # 21
    'device_os_encoded',        # 22
    'click_to_install_time_sec', # 23
    'has_recent_install',       # 24
    'install_broadcast_detected', # 25
    'click_injection_risk_score', # 26
    'conversion_rate',          # 27
    'engagement_score',        # 28
    # Label (is_fraud) is column 29
]
```

**Example Output Format**:
```csv
10.0,5.0,2.0,14,2,0,0.5,0,0,0,0,0,0.0,0,50,0.1,0.3,0.2,0,0,0.0,0,0,0.0,0,0,0,0.0,0.1,1
8.0,3.0,5.0,15,2,0,0.5,0,0,0,0,0,0.0,1,100,0.05,0.8,0.6,1,0,0.0,1,2,0.0,0,0,0,0.3,0.5,0
...
```

**Note**: No header row, label is last column (1 = fraud, 0 = legitimate)

---

### Step 9: Save to S3

**Location**: `scripts/process_training_data_sagemaker.py` (lines 93-137, 347-375)

**What Happens**:
1. Saves train/val/test DataFrames to CSV files
2. Optionally compresses with gzip (if `--compress` flag used)
3. Uploads to S3
4. Saves `metrics.json` with class imbalance info

**S3 Structure**:
```
s3://bucket/fraud-detection/training/processed/
├── train.csv.gz          # Training data (compressed)
├── val.csv.gz            # Validation data (compressed)
├── test.csv.gz           # Test data (compressed)
└── metrics.json          # Class imbalance metrics
```

**Code**:
```python
# Save CSV (no header, no index)
df.to_csv(filepath, header=False, index=False, compression='gzip')

# Upload to S3
s3_client.upload_file(local_file, bucket, s3_key)

# Save metrics
metrics = {
    'train': train_metrics,
    'validation': val_metrics,
    'test': test_metrics,
    'scale_pos_weight': train_metrics['scale_pos_weight'],
    'feature_count': 29,
    'feature_names': FEATURE_NAMES
}
s3_client.put_object(Bucket=bucket, Key='metrics.json', Body=json.dumps(metrics))
```

**Result**: Processed data ready for SageMaker training in S3

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Load Raw Data from S3                                   │
│ Input: s3://bucket/raw/train.csv                                 │
│ Output: pandas DataFrame with TalkingData columns               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Label Conversion                                        │
│ is_attributed=0 → is_fraud=1                                    │
│ is_attributed=1 → is_fraud=0                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Feature Engineering                                     │
│ - Aggregated features (IP/device click counts)                  │
│ - Temporal features (hour, day of week)                         │
│ - IP reputation features                                        │
│ - Device features                                               │
│ - Campaign/publisher features                                   │
│ - Engagement features                                           │
│ Result: 29 features + is_fraud label                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Preprocessing                                           │
│ - Handle missing values (fill with 0.0)                         │
│ - Encode categorical features                                   │
│ - Validate data (all numeric, no infinite values)               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Data Splitting                                          │
│ 70% train, 15% validation, 15% test                            │
│ (Stratified to maintain class distribution)                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Calculate Metrics                                       │
│ - Class distribution                                            │
│ - scale_pos_weight = sqrt(num_legitimate / num_fraud)           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 7: Optional SMOTE (if --use-smote)                        │
│ - Balance classes to 50/50                                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 8: Format for SageMaker                                    │
│ - Select features in exact order (29 features)                  │
│ - Add label as last column                                      │
│ - Remove header, ensure all numeric                             │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Step 9: Save to S3                                              │
│ - train.csv.gz, val.csv.gz, test.csv.gz                         │
│ - metrics.json                                                  │
│ Output: s3://bucket/processed/                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Files and Their Roles

### Processing Scripts

1. **`scripts/process_training_data_sagemaker.py`**
   - Main entry point for SageMaker Processing Job
   - Orchestrates all steps
   - Handles S3 I/O

2. **`scripts/process_training_data.py`**
   - Local processing script (same logic, runs locally)
   - Helper functions: `format_for_sagemaker()`, `calculate_class_imbalance_metrics()`

### Feature Engineering

3. **`training/feature_engineering.py`**
   - `engineer_talkingdata_features()` - Main feature engineering function
   - `compute_aggregated_features()` - Time-based aggregations
   - `FEATURE_NAMES` - List of 29 features in order

### Preprocessing

4. **`training/preprocessing.py`**
   - `preprocess_features()` - Handles missing values, encoding
   - Data validation

### Data Splitting

5. **`training/data_splitting.py`**
   - `split_data()` - Train/val/test splitting with stratification

---

## Running the Processing Pipeline

### Option 1: SageMaker Processing Job (Recommended)

```bash
python scripts/launch_sagemaker_processing_job.py \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --input-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/training/raw/ \
    --output-s3-path s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/ \
    --sagemaker-role-arn <ROLE_ARN> \
    --data-source talkingdata \
    --compress
```

### Option 2: Local Processing

```bash
python scripts/process_training_data.py \
    --data-source talkingdata \
    --output s3://bucket/fraud-detection/training/processed/ \
    --compress
```

---

## Verification

After processing, verify the output:

```bash
# Check S3 files
aws s3 ls s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/

# Check metrics
aws s3 cp s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/metrics.json - | python3 -m json.tool

# Sample a few rows (decompress first)
aws s3 cp s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/train.csv.gz - | gunzip | head -5
```

**Expected Output**:
- 3 CSV files (train, val, test) - no headers, label last column
- `metrics.json` with class distribution and `scale_pos_weight`
- All files compressed with gzip (if `--compress` used)

---

## Important Notes

1. **Feature Order is Critical**: Features must be in exact order matching `FEATURE_NAMES` in `feature_engineering.py`

2. **Label Position**: Label (`is_fraud`) must be the **last column** in SageMaker format

3. **No Headers**: SageMaker CSV format has **no header row**

4. **All Numeric**: All values must be numeric (no strings, no NaN, no infinite)

5. **Class Imbalance**: Your data is 99.71% fraud - this is expected for TalkingData. Use `scale_pos_weight` to handle it.

---

## Next Steps

After processing:
1. ✅ Verify data in S3
2. ✅ Check `metrics.json` for `scale_pos_weight`
3. ✅ Proceed to training: `docs/BOT_TRAFFIC_TRAINING_GUIDE.md` Step 3

