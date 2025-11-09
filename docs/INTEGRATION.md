# ML Model Integration Guide

This document describes how the ML model is integrated with the API for real-time fraud detection.

## Architecture Flow

```
1. Client → API Gateway → Ingestion Handler Lambda
   ↓
2. Ingestion Handler:
   - Validates event
   - Enriches with metadata
   - Stores in DynamoDB and S3
   - Triggers Orchestrator (async)
   ↓
3. Orchestrator Lambda:
   - Extracts features from event
   - Gets context data from DynamoDB
   - Calls SageMaker endpoint for ML score
   ↓
4. Decision Logic:
   - ML score > 0.8 → Block (fraud)
   - ML score < 0.3 → Allow (legitimate)
   - 0.3 ≤ ML score ≤ 0.8 → Route to AI analysis
   ↓
5. AI Analyzer Lambda (if needed):
   - Deep analysis using Bedrock Claude
   - Ensemble scoring with ML
   ↓
6. Store result in DynamoDB
   ↓
7. Return response to client
```

## Feature Extraction

The `feature_extractor.py` module extracts all 20 features required by the XGBoost model:

1. **Behavioral Features**:
   - `ip_click_count_24h`: Clicks from IP in last 24 hours
   - `device_click_count_1h`: Clicks from device in last hour
   - `time_since_last_click`: Seconds since last click

2. **Temporal Features**:
   - `hour_of_day`: Hour of day (0-23)
   - `day_of_week`: Day of week (0-6)

3. **User Agent Features**:
   - `ua_is_bot`: Boolean indicating bot user agent
   - `ua_entropy`: User agent string entropy (0-1)

4. **IP Reputation Features**:
   - `ip_is_datacenter`: Boolean indicating datacenter IP
   - `ip_is_vpn`: Boolean indicating VPN IP
   - `geo_distance_km`: Geographic distance

5. **Context Features**:
   - `referrer_is_valid`: Boolean indicating valid referrer
   - `click_to_view_time_ms`: Time on page before click

6. **Historical Features**:
   - `campaign_fraud_rate`: Historical fraud rate for campaign
   - `publisher_quality`: Publisher quality score

7. **Device Features**:
   - `device_fingerprint_entropy`: Device uniqueness score
   - `is_mobile`: Boolean indicating mobile device
   - `is_repeated_click`: Boolean indicating duplicate click

8. **Other Features**:
   - `time_to_conversion_sec`: Time to conversion
   - `ip_country`: Country code (encoded)
   - `device_os`: Operating system (encoded)

## SageMaker Integration

### Endpoint Invocation

The orchestrator calls the SageMaker endpoint with CSV-formatted features:

```python
# Convert features to CSV
csv_buffer = io.StringIO()
writer = csv.writer(csv_buffer)
writer.writerow(feature_vector)
csv_data = csv_buffer.getvalue()

# Invoke endpoint
response = sagemaker.invoke_endpoint(
    EndpointName=SAGEMAKER_ENDPOINT,
    ContentType='text/csv',
    Body=csv_data.encode('utf-8')
)

# Parse response (XGBoost returns probability 0-1)
prediction = float(response['Body'].read().decode('utf-8').strip())
```

### Response Format

- **Input**: CSV format with 20 feature values
- **Output**: Single float value (0.0-1.0) representing fraud probability

## Decision Logic

The orchestrator implements the two-tier detection logic:

```python
if ml_score > 0.8:
    # Clear fraud - block immediately
    return ml_only_response(is_fraud=True, action='block')
elif ml_score < 0.3:
    # Clear legitimate - allow immediately
    return ml_only_response(is_fraud=False, action='allow')
else:
    # Borderline case - route to AI analysis
    return route_to_ai_analysis(...)
```

## Error Handling

### SageMaker Endpoint Errors

- **Endpoint Not Available**: Falls back to placeholder score (0.5)
- **Timeout**: Falls back to placeholder score
- **Invalid Response**: Falls back to placeholder score

### Fallback Behavior

- If SageMaker fails, use placeholder score (0.5)
- If AI analysis fails, use ML-only result
- Always return a response (never fail completely)

## Testing

### Integration Tests

Run end-to-end integration tests:

```bash
# Install dependencies
pip install -r tests/requirements.txt

# Run tests
python tests/test_api_integration.py \
  --api-url https://your-api.execute-api.us-east-1.amazonaws.com/prod \
  --api-key your-api-key \
  --num-tests 100 \
  --output test_results.json
```

### Test Scenarios

1. **Fraudulent Events**: High click counts, bot user agents, datacenter IPs
2. **Legitimate Events**: Normal click patterns, valid user agents
3. **Borderline Events**: Scores between 0.3 and 0.8 (trigger AI analysis)

## Performance Requirements

From PRD:
- **ML Path Latency**: <100ms @ p95
- **AI Path Latency**: <3000ms @ p95
- **Throughput**: 1000 req/sec sustained

## Monitoring

### CloudWatch Metrics

- `SageMakerEndpointInvocations`: Number of endpoint calls
- `SageMakerEndpointModelLatency`: Prediction latency
- `SageMakerEndpointInvocationErrors`: Error count

### Custom Metrics

- `FraudDetected`: Count of fraud detections
- `MLScore`: Distribution of ML scores
- `DetectionMethod`: ML-only vs ML+AI ensemble

## Troubleshooting

### Common Issues

1. **High Latency**: Check SageMaker endpoint instance type and auto-scaling
2. **Incorrect Predictions**: Verify feature extraction matches training data
3. **Endpoint Errors**: Check IAM permissions and endpoint status
4. **Import Errors**: Ensure feature_extractor.py is included in Lambda package

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check CloudWatch Logs:
- `/aws/lambda/fraudguard-orchestrator`
- `/aws/lambda/fraudguard-ingestion-handler`

## Next Steps

1. Deploy updated Lambda functions
2. Test with real traffic
3. Monitor performance metrics
4. Tune decision thresholds based on results
5. Optimize feature extraction for latency

