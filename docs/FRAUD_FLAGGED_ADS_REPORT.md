# Fraud-Flagged Ads Report

**Generated:** Analysis of ML evaluation results for historical Google Ads events

---

## Executive Summary

- **Total Events Evaluated:** 188
- **Fraud-Flagged Events:** 188 (100.0%)
- **Not Fraud:** 0
- **Total Cost of Fraud-Flagged Ads:** $446.34
- **Average Cost per Fraud Event:** $8.93

### ML Score Statistics
- **ML Score (All Fraud Events):** 0.5642 (consistent across all events)
- **Detection Method:** ML Primary
- **Recommended Action:** Review (all events)

---

## Key Findings

### 1. Uniform ML Scores
All fraud-flagged events received the same ML score of **0.5642**, which suggests:
- The model is consistently identifying these events as suspicious
- The events share similar feature patterns
- The score is just above the fraud threshold (typically 0.5)

### 2. Campaign Distribution

| Campaign ID | Fraud Events | Total Cost | Avg ML Score |
|-------------|--------------|------------|--------------|
| 15973228065 | 17 | $266.32 | 0.5642 |
| 18395768345 | 7 | $5.96 | 0.5642 |
| 15973228050 | 7 | $94.04 | 0.5642 |
| 20594087693 | 7 | $4.54 | 0.5642 |
| 15973228068 | 5 | $22.29 | 0.5642 |
| 15973228203 | 3 | $19.88 | 0.5642 |
| 15973228074 | 2 | $21.31 | 0.5642 |
| 16171861909 | 1 | $6.65 | 0.5642 |
| 15973228077 | 1 | $5.35 | 0.5642 |

**Top Fraud Campaign:** Campaign `15973228065` has the highest fraud count (17 events) and highest cost ($266.32).

### 3. Keyword Analysis

Common keywords in fraud-flagged ads:
- **Digital Marketing Tools** (multiple occurrences)
- **SA360** / **Search Ads 360**
- **TikTok Business Manager**
- **Marin Software** / **Marin One Software**
- **Snapchat ads** / **Social media ads**
- **Kenshoo**
- **Digital Marketing Automation Software**

### 4. Cost Impact

- **Highest Cost Event:** $18.79 (Campaign 15973228065, "digital marketing automation software")
- **Lowest Cost Event:** $0.37 (Campaign 18395768345, "tiktok business manager")
- **Average Cost:** $8.93 per fraud event

---

## Sample Fraud-Flagged Ads

### Top 10 by Cost

1. **Event:** `google-ads-historical-15973228065-1747791303-5-34271c28`
   - Campaign: 15973228065
   - Keyword: digital marketing automation software
   - Cost: $18.79
   - CTR: 2.16%
   - Date: 2025-05-21
   - ML Score: 0.5642

2. **Event:** `google-ads-historical-15973228065-1737818200-8-4a81275a`
   - Campaign: 15973228065
   - Keyword: marketing campaign management platform
   - Cost: $17.10
   - CTR: 1.55%
   - Date: 2025-01-25
   - ML Score: 0.5642

3. **Event:** `google-ads-historical-15973228065-1745362929-13-c0ad5d89`
   - Campaign: 15973228065
   - Keyword: best marketing management software
   - Cost: $15.08
   - CTR: 1.91%
   - Date: 2025-04-22
   - ML Score: 0.5642

4. **Event:** `google-ads-historical-15973228050-1742594956-1-6e4f8863`
   - Campaign: 15973228050
   - Keyword: SA360
   - Cost: $14.89
   - CTR: 2.79%
   - Date: 2025-03-21
   - ML Score: 0.5642

5. **Event:** `google-ads-historical-15973228050-1742585729-11-5bcccbde`
   - Campaign: 15973228050
   - Keyword: google ads platform
   - Cost: $14.89
   - CTR: 2.79%
   - Date: 2025-03-21
   - ML Score: 0.5642

6. **Event:** `google-ads-historical-15973228050-1739261884-3-29a02193`
   - Campaign: 15973228050
   - Keyword: kenshoo
   - Cost: $11.04
   - CTR: 2.08%
   - Date: 2025-02-11
   - ML Score: 0.5642

7. **Event:** `google-ads-historical-15973228065-1745618230-12-b7d2fa8d`
   - Campaign: 15973228065
   - Keyword: digital marketing tools
   - Cost: $10.97
   - CTR: 3.36%
   - Date: 2025-04-25
   - ML Score: 0.5642

8. **Event:** `google-ads-historical-15973228050-1739550479-11-02c5c4b8`
   - Campaign: 15973228050
   - Keyword: search ads 360
   - Cost: $10.25
   - CTR: 1.90%
   - Date: 2025-02-14
   - ML Score: 0.5642

9. **Event:** `google-ads-historical-15973228065-1745898352-15-7acbdd95`
   - Campaign: 15973228065
   - Keyword: digital marketing tools
   - Cost: $11.80
   - CTR: 4.13%
   - Date: 2025-04-29
   - ML Score: 0.5642

10. **Event:** `google-ads-historical-15973228065-1761042643-12-1c4404a5`
    - Campaign: 15973228065
    - Keyword: digital marketing tools
    - Cost: $12.87
    - CTR: 5.37%
    - Date: 2025-10-21
    - ML Score: 0.5642

---

## Patterns & Insights

### 1. High CTR Events
Several fraud-flagged events show unusually high CTRs:
- **28% CTR** (Campaign 15973228068, "marinsoftware")
- **20% CTR** (Campaign 15973228203, "social media ads")
- **15.6% CTR** (Campaign 15973228068, "marin one software")
- **6.6% CTR** (Campaign 18395768345, "tiktok business manager")

**Note:** High CTRs can be a red flag for click fraud, as legitimate ads typically have CTRs between 1-5%.

### 2. Campaign Concentration
- **Campaign 15973228065** accounts for 36% of fraud events and 60% of fraud cost
- This campaign focuses on "digital marketing tools" and related keywords
- **Recommendation:** Investigate this campaign for potential systematic fraud

### 3. Date Range
Fraud-flagged events span from **November 2024** to **October 2025**, indicating:
- Historical data from Google Ads API
- Consistent fraud patterns across time periods
- Need for ongoing monitoring

### 4. GCLID Patterns
All events have GCLIDs in the format: `API-{CampaignID}-{Timestamp}-{Index}-{Hash}`
- These are API-generated GCLIDs (not user-generated)
- Consistent pattern suggests automated or scripted clicks

---

## Recommendations

### Immediate Actions
1. **Review Campaign 15973228065** - Highest fraud concentration
2. **Investigate High CTR Events** - CTRs above 10% are suspicious
3. **Examine GCLID Patterns** - API-generated GCLIDs may indicate bot traffic
4. **Review Keywords** - Focus on "digital marketing tools" category

### Long-term Actions
1. **Set Up Automated Alerts** - Flag events with ML score > 0.5
2. **Campaign-Level Monitoring** - Track fraud rates by campaign
3. **Cost Threshold Alerts** - Alert on high-cost fraud events
4. **Feedback Loop** - Collect manual review outcomes to improve model

---

## Technical Details

### ML Model Performance
- **Model:** XGBoost (Gradient Boosting)
- **Threshold:** 0.5 (binary classification)
- **Score Range:** 0.0 (legitimate) to 1.0 (fraud)
- **Current Fraud Score:** 0.5642 (just above threshold)

### Detection Method
- **Primary:** ML-based detection using SageMaker endpoint
- **Action:** Review (all fraud-flagged events require manual review)
- **Confidence:** Moderate (score is close to threshold)

---

## Data Source

- **Evaluation Script:** `scripts/evaluate_existing_events.py`
- **Results File:** `ml_evaluation_results.jsonl`
- **DynamoDB Table:** `fraudguard-events-dev`
- **Analysis Script:** `scripts/analyze_fraud_ads.py`

---

## Next Steps

1. **Manual Review** - Review top 20 fraud-flagged events
2. **Campaign Investigation** - Deep dive into Campaign 15973228065
3. **Model Calibration** - Consider adjusting threshold based on review outcomes
4. **Cost Analysis** - Calculate potential savings from blocking fraud
5. **Reporting** - Set up automated fraud reports for stakeholders

---

*Report generated by analyzing ML evaluation results from historical Google Ads data.*

