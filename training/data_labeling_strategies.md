# Data Labeling Strategies for Google Ads Training Data

## Current Situation

- **Total items**: 9,813
- **Labeled fraud**: 22 (0.22%)
- **Labeled legitimate**: 9,613 (97.96%)
- **Unlabeled**: 178 (1.81%)
- **Suspicious legitimate items**: 53 (0.6%) with fraud signals but labeled legitimate

## Analysis Findings

### Fraud Score Distribution
- **Fraud items**: Scores 0.68-0.78 (mean: 0.73) - clear fraud
- **Legitimate items**: Scores 0.00-0.44 (mean: 0.003) - mostly clean
- **Gap**: No legitimate items with scores > 0.5 (clear separation)
- **Borderline cases**: 53 items with scores 0.3-0.44 and fraud signals

### Suspicious Patterns Found
- 53 legitimate items have fraud signals (mostly "borderline_ml_score")
- 2 items have scores > 0.4 but labeled legitimate
- These might be false negatives (undetected fraud)

---

## Recommended Training Strategies

### Strategy 1: Semi-Supervised Learning with Soft Labels ⭐⭐⭐⭐⭐

**Best for**: Maximizing use of all data while handling uncertainty

**Approach**:
1. Use fraud scores as soft labels (continuous 0-1 instead of binary)
2. Treat high-confidence cases (score > 0.7) as hard labels
3. Use medium-confidence cases (0.3-0.7) as soft labels with lower weight
4. Low-confidence cases (< 0.3) as legitimate with full weight

**Implementation**:
```python
def create_soft_labels(item):
    """Create soft labels from fraud scores"""
    fraud_score = float(item.get('fraud_score', 0))
    is_fraud_hard = item.get('is_fraud', False)
    
    # High confidence fraud
    if fraud_score > 0.7 or is_fraud_hard:
        return 1.0, 1.0  # (label, weight)
    
    # Medium confidence (suspicious)
    elif fraud_score > 0.3:
        return fraud_score, 0.5  # Soft label with reduced weight
    
    # Low confidence (legitimate)
    else:
        return 0.0, 1.0

# Apply to all items
df['fraud_label'] = df.apply(lambda row: create_soft_labels(row)[0], axis=1)
df['sample_weight'] = df.apply(lambda row: create_soft_labels(row)[1], axis=1)
```

**Advantages**:
- Uses all 9,813 items
- Handles uncertainty gracefully
- Doesn't require manual relabeling
- Works well with XGBoost (supports sample weights)

**Disadvantages**:
- More complex implementation
- Requires careful weight tuning

---

### Strategy 2: Rule-Based Re-labeling ⭐⭐⭐⭐

**Best for**: Quick improvement with clear rules

**Approach**:
1. Define rules to identify likely fraud cases
2. Re-label suspicious legitimate items
3. Use conservative thresholds to avoid false positives

**Rules**:
```python
def should_relabel_as_fraud(item):
    """Determine if item should be relabeled as fraud"""
    fraud_score = float(item.get('fraud_score', 0))
    signals = item.get('fraud_signals', [])
    signal_count = len(signals) if isinstance(signals, list) else 0
    
    # Rule 1: High score with multiple signals
    if fraud_score > 0.45 and signal_count >= 3:
        return True
    
    # Rule 2: Multiple strong fraud signals
    strong_signals = ['datacenter_ip', 'headless_browser', 'impersonated_device']
    strong_signal_count = sum(1 for s in signals if s in strong_signals)
    if strong_signal_count >= 2:
        return True
    
    # Rule 3: High score with specific fraud type indicators
    if fraud_score > 0.4 and 'low_device_entropy' in signals:
        return True
    
    return False

# Apply relabeling
for item in suspicious_legit_items:
    if should_relabel_as_fraud(item):
        item['is_fraud'] = True
        item['relabeled'] = True  # Track for analysis
```

**Expected Impact**:
- Could add 5-15 more fraud cases (conservative estimate)
- Total fraud cases: 27-37 (0.27-0.38%)

**Advantages**:
- Simple to implement
- Transparent rules
- Can track relabeled items

**Disadvantages**:
- May introduce some false positives
- Requires domain expertise for rules

---

### Strategy 3: Active Learning / Human-in-the-Loop ⭐⭐⭐

**Best for**: Highest quality labels with human review

**Approach**:
1. Identify most uncertain cases for human review
2. Prioritize items with:
   - Fraud scores 0.3-0.5
   - Multiple fraud signals
   - High cost or suspicious patterns
3. Human reviewers label these cases
4. Retrain model with new labels

**Prioritization**:
```python
def prioritize_for_review(item):
    """Calculate priority score for human review"""
    fraud_score = float(item.get('fraud_score', 0))
    signals = item.get('fraud_signals', [])
    cost = float(item.get('cost_micros', 0)) / 1_000_000  # Convert to dollars
    
    # Uncertainty score (highest at 0.5, decreases toward 0 or 1)
    uncertainty = 1 - abs(fraud_score - 0.5) * 2
    
    # Signal count bonus
    signal_bonus = min(len(signals) / 5, 1.0)
    
    # Cost bonus (higher cost = more important)
    cost_bonus = min(cost / 100, 1.0)  # Normalize to $100
    
    priority = (uncertainty * 0.4 + signal_bonus * 0.3 + cost_bonus * 0.3)
    return priority

# Get top 100 items for review
review_candidates = sorted(all_items, key=prioritize_for_review, reverse=True)[:100]
```

**Advantages**:
- Highest label quality
- Can catch edge cases
- Builds labeled dataset over time

**Disadvantages**:
- Requires human time
- Slower process
- May not scale well

---

### Strategy 4: Combine with TalkingData (Recommended) ⭐⭐⭐⭐⭐

**Best for**: Best overall training results

**Approach**:
1. **Primary training**: Use TalkingData (185M records, better balance)
2. **Domain adaptation**: Use Google Ads data for fine-tuning
3. **Validation/Testing**: Use Google Ads data for domain-specific evaluation

**Implementation**:
```python
# Load both datasets
talkingdata = loader.load_talkingdata(use_sample=False, nrows=1_000_000)
google_ads = loader.load_google_ads_data()

# Train on TalkingData
model.fit(
    X_train_talkingdata,
    y_train_talkingdata,
    eval_set=[(X_val_talkingdata, y_val_talkingdata)]
)

# Fine-tune on Google Ads (with class weights)
model.fit(
    X_train_google_ads,
    y_train_google_ads,
    xgb_model=model.get_booster(),  # Continue training
    sample_weight=calculate_class_weights(y_train_google_ads)
)
```

**Advantages**:
- Leverages large TalkingData dataset
- Domain-specific adaptation
- Better class balance
- Google Ads data used where it's most valuable

**Disadvantages**:
- Requires more data processing
- Two-stage training

---

### Strategy 5: Weak Supervision with Snorkel ⭐⭐⭐

**Best for**: Automated labeling at scale

**Approach**:
1. Define labeling functions (LFs) based on fraud signals
2. Use Snorkel to combine LFs and create probabilistic labels
3. Train model on weakly labeled data

**Labeling Functions**:
```python
from snorkel.labeling import labeling_function

@labeling_function()
def high_fraud_score(x):
    return 1 if x.fraud_score > 0.6 else 0

@labeling_function()
def datacenter_ip_signal(x):
    return 1 if 'datacenter_ip' in x.fraud_signals else 0

@labeling_function()
def multiple_signals(x):
    return 1 if len(x.fraud_signals) >= 3 else 0

# Combine LFs with Snorkel
from snorkel.labeling import LabelModel
label_model = LabelModel(cardinality=2)
label_model.fit(L_train)  # L_train is matrix of LF outputs
prob_labels = label_model.predict_proba(L_train)
```

**Advantages**:
- Automated labeling
- Handles conflicting signals
- Can scale to large datasets

**Disadvantages**:
- Requires Snorkel setup
- More complex
- May need tuning

---

## Recommended Approach: Hybrid Strategy

### Phase 1: Immediate (Use Now)
1. **Use Strategy 4**: Train primarily on TalkingData, use Google Ads for validation
2. **Apply Strategy 1**: Use soft labels for Google Ads data in validation

### Phase 2: Short-term (1-2 weeks)
1. **Apply Strategy 2**: Rule-based relabeling of suspicious cases
2. **Re-evaluate**: Check if relabeled cases improve model performance

### Phase 3: Long-term (Ongoing)
1. **Implement Strategy 3**: Set up human review for high-priority cases
2. **Continuous improvement**: Retrain model as new labels are added

---

## Implementation Priority

1. **High Priority**: Strategy 4 (Combine with TalkingData) + Strategy 1 (Soft labels)
2. **Medium Priority**: Strategy 2 (Rule-based relabeling)
3. **Low Priority**: Strategy 3 (Human review) or Strategy 5 (Snorkel)

---

## Code Example: Soft Labels Implementation

```python
import pandas as pd
import numpy as np
from training.data_loader import DataLoader

def create_training_data_with_soft_labels():
    """Create training data with soft labels from Google Ads data"""
    loader = DataLoader()
    df = loader.load_google_ads_data()
    
    def get_soft_label(row):
        """Convert fraud score to soft label with weight"""
        fraud_score = float(row.get('fraud_score', 0))
        is_fraud = row.get('is_fraud', False)
        
        # Hard label if explicitly marked as fraud
        if is_fraud:
            return 1.0, 1.0
        
        # Soft label based on score
        if fraud_score > 0.7:
            return 1.0, 1.0  # High confidence fraud
        elif fraud_score > 0.4:
            return fraud_score, 0.5  # Medium confidence (suspicious)
        elif fraud_score > 0.3:
            return fraud_score * 0.5, 0.3  # Low confidence (slightly suspicious)
        else:
            return 0.0, 1.0  # Legitimate
    
    # Apply soft labels
    labels_and_weights = df.apply(get_soft_label, axis=1)
    df['fraud_label'] = [lw[0] for lw in labels_and_weights]
    df['sample_weight'] = [lw[1] for lw in labels_and_weights]
    
    return df

# Use in XGBoost training
df = create_training_data_with_soft_labels()
X = df[feature_columns]
y = df['fraud_label']
sample_weight = df['sample_weight']

model.fit(X, y, sample_weight=sample_weight)
```

---

## Expected Outcomes

### With Current Labels Only
- **Fraud cases**: 22 (0.22%)
- **Training challenge**: Extreme imbalance
- **Risk**: Model may not learn fraud patterns well

### With Soft Labels
- **Effective fraud cases**: ~75-100 (including suspicious items)
- **Training improvement**: Better learning signal
- **Risk**: Lower (uncertainty handled via weights)

### With Rule-Based Relabeling
- **Fraud cases**: 27-37 (0.27-0.38%)
- **Training improvement**: More fraud examples
- **Risk**: Some false positives possible

### With Combined Approach (TalkingData + Google Ads)
- **Primary training**: 185M TalkingData records
- **Domain adaptation**: 9,813 Google Ads records
- **Best outcome**: Strong general model + domain-specific tuning

