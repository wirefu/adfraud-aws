# Next Steps After Training & Deployment

Congratulations! Your XGBoost model is trained and deployed. Here's what to do next.

---

## ✅ Current Status

- **Model Trained**: XGBoost model optimized for bot traffic detection
- **Endpoint Deployed**: `fraudguard-xgboost-endpoint` (InService)
- **Scale Pos Weight**: 0.0535 (handles class imbalance)
- **Features**: 29 features (29 base + 0 Google Ads specific in this dataset)

---

## Step 1: Verify Endpoint Configuration

### 1.1: Check Endpoint Status

```bash
aws sagemaker describe-endpoint \
    --endpoint-name fraudguard-xgboost-endpoint \
    --query 'EndpointStatus' \
    --output text
```

**Expected**: `InService`

### 1.2: Verify Lambda Configuration

Check if your Lambda function is configured to use the endpoint:

```bash
# Check current Lambda environment variable
aws lambda get-function-configuration \
    --function-name <your-orchestrator-function-name> \
    --query 'Environment.Variables.SAGEMAKER_ENDPOINT' \
    --output text
```

**Expected**: `fraudguard-xgboost-endpoint`

If it's different or missing, update it (see Step 2).

---

## Step 2: Update Lambda Environment Variable (If Needed)

Your Lambda orchestrator needs to know which endpoint to call.

### Option A: Update via AWS Console

1. Go to: AWS Console → Lambda → Functions → `fraudguard-ai-dev-orchestrator`
2. Click **Configuration** → **Environment variables**
3. Update or add: `SAGEMAKER_ENDPOINT = fraudguard-xgboost-endpoint`
4. Click **Save**

### Option B: Update via AWS CLI

```bash
aws lambda update-function-configuration \
    --function-name <your-orchestrator-function-name> \
    --environment "Variables={SAGEMAKER_ENDPOINT=fraudguard-xgboost-endpoint}"
```

### Option C: Update via SAM/Template

If using SAM, update `template.yaml`:

```yaml
Orchestrator:
  Type: AWS::Serverless::Function
  Properties:
    Environment:
      Variables:
        SAGEMAKER_ENDPOINT: 'fraudguard-xgboost-endpoint'  # ✅ Update this
```

Then redeploy:
```bash
sam build && sam deploy
```

---

## Step 3: Test the Endpoint

### 3.1: Test with Sample Features

Create a test script to verify the endpoint works:

```python
import boto3
import json

# Create SageMaker runtime client
runtime = boto3.client('sagemaker-runtime')

# Sample feature vector (29 features in order)
# This represents a suspicious bot-like event
sample_features = [
    10.0,   # ip_click_count_24h (high)
    5.0,    # device_click_count_1h (high)
    2.0,    # time_since_last_click (very short)
    14,     # hour_of_day
    2,      # day_of_week
    1.0,    # ua_is_bot (True - bot detected)
    0.2,    # ua_entropy (low - suspicious)
    0.0,    # ip_is_datacenter
    0.0,    # ip_is_vpn
    0.0,    # ip_is_proxy
    0.0,    # ip_is_business
    0.0,    # ip_is_competitor
    0.0,    # geo_distance_km
    0.0,    # referrer_is_valid (False - no referrer)
    50,     # click_to_view_time_ms (very short)
    0.1,    # campaign_fraud_rate
    0.3,    # publisher_quality (low)
    0.2,    # device_fingerprint_entropy (low)
    0.0,    # is_mobile
    0.0,    # is_repeated_click
    0.0,    # time_to_conversion_sec
    0,      # ip_country_encoded
    0,      # device_os_encoded
    0.0,    # click_to_install_time_sec
    0.0,    # has_recent_install
    0.0,    # install_broadcast_detected
    0.0,    # click_injection_risk_score
    0.0,    # conversion_rate
    0.1,    # engagement_score (low)
]

# Convert to CSV format (SageMaker expects CSV)
feature_csv = ','.join(map(str, sample_features))

# Invoke endpoint
response = runtime.invoke_endpoint(
    EndpointName='fraudguard-xgboost-endpoint',
    ContentType='text/csv',
    Body=feature_csv
)

# Parse response
prediction = float(response['Body'].read().decode('utf-8').strip())
print(f"Bot Traffic Score: {prediction:.4f}")
print(f"Prediction: {'BOT' if prediction > 0.5 else 'LEGITIMATE'}")
```

**Expected Output**:
- Score should be > 0.5 (likely bot) for the sample above
- Response time < 100ms

### 3.2: Test with Real Data

Test with actual events from your system:

```python
# Load a real event from DynamoDB
import boto3
from src.orchestrator.feature_extractor import extract_features

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ad-events')

# Get a sample event
response = table.scan(Limit=1)
event = response['Items'][0]

# Extract features
features = extract_features(event)

# Call endpoint
runtime = boto3.client('sagemaker-runtime')
feature_csv = ','.join(map(str, features))

response = runtime.invoke_endpoint(
    EndpointName='fraudguard-xgboost-endpoint',
    ContentType='text/csv',
    Body=feature_csv
)

prediction = float(response['Body'].read().decode('utf-8').strip())
print(f"ML Score: {prediction:.4f}")
```

---

## Step 4: Test End-to-End Integration

### 4.1: Test via API Gateway

Send a test event through your API:

```bash
# Test Google Ads tracking endpoint
curl -X POST https://<your-api-id>.execute-api.us-east-1.amazonaws.com/prod/api/track \
  -H "Content-Type: application/json" \
  -d '{
    "gclid": "test-gclid-123",
    "cid": "test-campaign",
    "kw": "test keyword"
  }'
```

### 4.2: Check Lambda Logs

Monitor the orchestrator Lambda to see if it's calling SageMaker:

```bash
aws logs tail /aws/lambda/<your-orchestrator-function-name> --follow
```

**Look for**:
- `Calling SageMaker endpoint: fraudguard-xgboost-endpoint`
- `ML Score: 0.XXXX`
- No errors about endpoint not found

---

## Step 5: Evaluate Model Performance

### 5.1: Get Training Metrics

```bash
# Get the best training job from HPO
HPO_JOB=$(aws sagemaker list-hyper-parameter-tuning-jobs \
    --name-contains "fraudguard-xgboost" \
    --max-results 1 \
    --sort-by CreationTime \
    --sort-order Descending \
    --query 'HyperParameterTuningJobSummaries[0].HyperParameterTuningJobName' \
    --output text)

# Get best training job
BEST_JOB=$(aws sagemaker list-training-jobs-for-hyper-parameter-tuning-job \
    --hyper-parameter-tuning-job-name "$HPO_JOB" \
    --sort-by FinalObjectiveMetricValue \
    --sort-order Descending \
    --max-results 1 \
    --query 'TrainingJobSummaries[0].TrainingJobName' \
    --output text)

# Get metrics
aws sagemaker describe-training-job \
    --training-job-name "$BEST_JOB" \
    --query 'FinalMetricDataList[*].{MetricName:MetricName,Value:Value}' \
    --output table
```

### 5.2: Evaluate on Test Set

Use the evaluation script:

```bash
python3 scripts/evaluate_model.py \
    --endpoint-name fraudguard-xgboost-endpoint \
    --s3-bucket fraudguard-ai-data-971422717446 \
    --test-data s3://fraudguard-ai-data-971422717446/fraud-detection/training/processed/test.csv.gz \
    --sample-size 1000
```

**Expected Metrics** (for bot traffic detection):
- **Precision**: > 0.85 (low false positives)
- **Recall**: > 0.80 (catch most bots)
- **F1 Score**: > 0.82
- **ROC AUC**: > 0.95

---

## Step 6: Monitor Production Performance

### 6.1: Set Up CloudWatch Dashboards

Monitor key metrics:

**SageMaker Endpoint Metrics**:
- `SageMakerEndpointInvocations`: Number of predictions
- `SageMakerEndpointModelLatency`: Prediction latency (should be < 100ms)
- `SageMakerEndpointInvocationErrors`: Error count (should be 0)
- `SageMakerEndpointInvocation4XXErrors`: Client errors
- `SageMakerEndpointInvocation5XXErrors`: Server errors

**Lambda Metrics**:
- `Invocations`: Number of events processed
- `Duration`: Processing time
- `Errors`: Error count
- `Throttles`: Throttling events

### 6.2: Set Up Alarms

Create CloudWatch alarms for:

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
    --alarm-name sagemaker-endpoint-errors \
    --alarm-description "Alert on SageMaker endpoint errors" \
    --metric-name SageMakerEndpointInvocationErrors \
    --namespace AWS/SageMaker \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 1 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold

# High latency alarm
aws cloudwatch put-metric-alarm \
    --alarm-name sagemaker-endpoint-latency \
    --alarm-description "Alert on high prediction latency" \
    --metric-name SageMakerEndpointModelLatency \
    --namespace AWS/SageMaker \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 500 \
    --comparison-operator GreaterThanThreshold
```

---

## Step 7: Optimize for Production (Optional)

### 7.1: Adjust Instance Type

For production traffic, consider upgrading:

**Current**: `ml.t2.medium` (~$0.065/hour)
**Recommended for Production**: `ml.m5.large` (~$0.115/hour)

Benefits:
- Better performance (lower latency)
- More consistent response times
- Better for higher traffic

```bash
# Update endpoint configuration
aws sagemaker update-endpoint \
    --endpoint-name fraudguard-xgboost-endpoint \
    --endpoint-config-name <new-config-name>
```

### 7.2: Enable Auto-Scaling

Automatically scale endpoint based on traffic:

```bash
aws application-autoscaling register-scalable-target \
    --service-namespace sagemaker \
    --scalable-dimension sagemaker:variant:DesiredInstanceCount \
    --resource-id endpoint/fraudguard-xgboost-endpoint/variant/AllTraffic \
    --min-capacity 1 \
    --max-capacity 3 \
    --role-arn <autoscaling-role-arn>

# Create scaling policy
aws application-autoscaling put-scaling-policy \
    --service-namespace sagemaker \
    --scalable-dimension sagemaker:variant:DesiredInstanceCount \
    --resource-id endpoint/fraudguard-xgboost-endpoint/variant/AllTraffic \
    --policy-name scale-on-cpu \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
        "TargetValue": 70.0,
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
        }
    }'
```

### 7.3: Set Up A/B Testing (Optional)

Test new model versions against current:

```bash
# Create new variant with updated model
# Then split traffic: 90% current, 10% new
```

---

## Step 8: Fine-Tune Bot Detection Threshold

Your model returns a score (0.0-1.0). You may want to adjust the threshold for bot detection:

### Current Thresholds (in `src/orchestrator/app.py`):

```python
FRAUD_THRESHOLD = 0.8      # Block immediately if ML score > 0.8
LEGITIMATE_THRESHOLD = 0.3  # Allow immediately if ML score < 0.3
BORDERLINE_MIN = 0.3       # Route to AI if score between 0.3 and 0.8
BORDERLINE_MAX = 0.8
```

### For Bot Traffic Detection:

You might want **lower thresholds** to catch more bots:

```python
# More aggressive bot detection
FRAUD_THRESHOLD = 0.5      # Block if score > 0.5 (more bots caught)
LEGITIMATE_THRESHOLD = 0.2  # Allow if score < 0.2
BORDERLINE_MIN = 0.2       # Route to AI if score between 0.2 and 0.5
BORDERLINE_MAX = 0.5
```

**To Update**:
1. Edit `src/orchestrator/app.py`
2. Adjust thresholds based on your evaluation results
3. Redeploy Lambda: `sam build && sam deploy`

---

## Step 9: Continuous Improvement

### 9.1: Monitor Model Drift

Track if model performance degrades over time:

- Monitor prediction distributions
- Track fraud rate changes
- Compare actual vs predicted fraud rates

### 9.2: Retrain Periodically

**Recommended**: Retrain every 1-3 months or when:
- New fraud patterns emerge
- Data distribution changes significantly
- Model performance degrades

**Retraining Process**:
1. Collect new training data
2. Process with same pipeline
3. Retrain with HPO (10 jobs)
4. Evaluate new model
5. A/B test against current model
6. Deploy if better

### 9.3: Collect Feedback

Track:
- False positives (legitimate traffic flagged as fraud)
- False negatives (fraud missed)
- Manual overrides
- User reports

Use this feedback to improve the model.

---

## Step 10: Documentation & Handoff

### 10.1: Document Model Details

Record:
- Model version/ID
- Training date
- Hyperparameters used
- Performance metrics
- Feature importance
- Known limitations

### 10.2: Create Runbook

Document:
- How to check endpoint status
- How to update endpoint
- How to rollback if issues occur
- Emergency procedures

---

## Quick Reference Commands

```bash
# Check endpoint status
aws sagemaker describe-endpoint --endpoint-name fraudguard-xgboost-endpoint

# Test endpoint
python3 -c "
import boto3
runtime = boto3.client('sagemaker-runtime')
features = ','.join(['0'] * 29)
response = runtime.invoke_endpoint(
    EndpointName='fraudguard-xgboost-endpoint',
    ContentType='text/csv',
    Body=features
)
print(float(response['Body'].read().decode('utf-8').strip()))
"

# Monitor logs
aws logs tail /aws/lambda/<orchestrator-function> --follow

# Check metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/SageMaker \
    --metric-name SageMakerEndpointInvocations \
    --dimensions Name=EndpointName,Value=fraudguard-xgboost-endpoint \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Sum
```

---

## Summary Checklist

- [ ] ✅ Verify endpoint is `InService`
- [ ] ✅ Update Lambda `SAGEMAKER_ENDPOINT` environment variable
- [ ] ✅ Test endpoint with sample features
- [ ] ✅ Test end-to-end integration (API → Lambda → SageMaker)
- [ ] ✅ Evaluate model on test set
- [ ] ✅ Set up CloudWatch monitoring
- [ ] ✅ Adjust bot detection thresholds (if needed)
- [ ] ✅ Document model details
- [ ] ✅ Plan for periodic retraining

---

## Need Help?

- **Endpoint Issues**: Check CloudWatch logs for `/aws/sagemaker/Endpoints`
- **Lambda Issues**: Check `/aws/lambda/<function-name>` logs
- **Performance Issues**: Review instance type and auto-scaling
- **Model Issues**: Re-evaluate on test set, consider retraining

---

**Congratulations on deploying your bot traffic detection model!** 🎉

