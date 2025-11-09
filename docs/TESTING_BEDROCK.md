# Testing Bedrock AI Analysis

This guide explains how to test the Bedrock AI analyzer Lambda function both locally and in AWS.

## Prerequisites

1. **AWS Credentials**: Configure AWS CLI with appropriate credentials
   ```bash
   aws configure
   ```

2. **Bedrock Model Access**: Request access to Claude 3.5 Sonnet in AWS Bedrock Console
   - Go to AWS Bedrock Console
   - Navigate to "Model access"
   - Request access for "Claude 3.5 Sonnet"
   - **Important**: Some regions may require using an "Inference Profile" instead of direct model ID

3. **IAM Permissions**: Ensure your AWS credentials have:
   - `bedrock:InvokeModel` permission
   - `lambda:InvokeFunction` permission (for deployed testing)

4. **Python Dependencies**: Install required packages
   ```bash
   pip install -r scripts/test_bedrock_requirements.txt
   ```

## Model ID Configuration

### Option 1: Direct Model ID (Older Format)

```bash
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

### Option 2: Inference Profile (Newer Format - Recommended)

If you get an error about "on-demand throughput isn't supported", you need to use an inference profile:

1. **Create Inference Profile** in AWS Bedrock Console:
   - Go to Bedrock Console → Inference → Inference profiles
   - Create a new profile
   - Add Claude 3.5 Sonnet model
   - Note the profile ID (e.g., `us.anthropic.claude-3-5-sonnet-20241022-v2:0`)

2. **Set Environment Variable**:
   ```bash
   export BEDROCK_MODEL_ID=<your-inference-profile-id>
   ```

3. **Or Update Lambda Environment Variable**:
   - In Lambda Console, go to Configuration → Environment variables
   - Set `BEDROCK_MODEL_ID` to your inference profile ID

## Testing Methods

### Method 1: Local Testing (Recommended for Development)

Test the Lambda function code directly without deploying to AWS.

**Advantages:**
- Fast iteration
- No deployment needed
- Easy debugging
- Lower cost (only Bedrock API calls)

**Steps:**

1. **Set Environment Variables**:
   ```bash
   # Option 1: Direct model ID (if supported in your region)
   export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   
   # Option 2: Inference profile (if direct model ID doesn't work)
   export BEDROCK_MODEL_ID=<your-inference-profile-id>
   
   export AWS_REGION=us-east-1
   ```

2. **Run Local Tests**:
   ```bash
   # Test with default events (3 tests)
   python scripts/test_bedrock_local.py
   
   # Test with custom number of events
   python scripts/test_bedrock_local.py --num-tests 5
   
   # Test with specific event file
   python scripts/test_bedrock_local.py --event-file tests/events/fraud_event.json
   
   # Save results to file
   python scripts/test_bedrock_local.py --num-tests 5 --output bedrock_test_results.json
   ```

3. **Expected Output**:
   ```
   ============================================================
   Bedrock AI Analysis Local Testing
   ============================================================
   
   ⚠️  Note: This requires AWS credentials and Bedrock model access
      Make sure BEDROCK_MODEL_ID is set or uses default
      Check IAM permissions for bedrock:InvokeModel
   
   Created 3 test events
     Fraud events: 1
     Legitimate events: 2
   
   ------------------------------------------------------------
   Running tests...
   ------------------------------------------------------------
   
   Test 1/3: test-fraud-123
     ML Score: 0.60
     IP: 10.0.0.1
     User Agent: HeadlessChrome/91.0.4472.124...
     ✅ Success
       Fraud: True
       AI Score: 0.8500
       Confidence: 0.9000
       Type: bot_traffic
       Signals: bot_user_agent, high_click_velocity, datacenter_ip
       Reasoning: This event shows clear signs of bot traffic...
   ```

### Method 2: Testing with SAM Local

Test using AWS SAM CLI's local invocation.

**Steps:**

1. **Build the application**:
   ```bash
   sam build
   ```

2. **Set Environment Variables** (if using inference profile):
   ```bash
   export BEDROCK_MODEL_ID=<your-inference-profile-id>
   ```

3. **Invoke AI Analyzer locally**:
   ```bash
   # Test with fraud event
   sam local invoke AIAnalyzer --event tests/events/fraud_event.json
   
   # Test with legitimate event
   sam local invoke AIAnalyzer --event tests/events/legitimate_event.json
   ```

4. **Note**: SAM local requires Docker to be running.

### Method 3: Testing Deployed Lambda (Production Testing)

Test the Lambda function after deployment to AWS.

**Prerequisites:**
- Lambda function must be deployed
- Function name must match your deployment

**Steps:**

1. **Deploy the Lambda function** (if not already deployed):
   ```bash
   sam build
   sam deploy --guided
   ```

2. **Get the function name** from deployment outputs or AWS Console

3. **Run tests against deployed Lambda**:
   ```bash
   python scripts/test_bedrock_ai.py \
     --function-name fraudguard-ai-analyzer \
     --num-tests 5 \
     --output bedrock_test_results.json
   ```

## Test Scenarios

### 1. Bot Traffic Detection

**Test Event**: `tests/events/fraud_event.json`

**Expected Results:**
- `is_fraud`: `true`
- `primary_fraud_type`: `bot_traffic`
- `fraud_signals`: Should include `bot_user_agent`, `high_click_velocity`
- `ai_score`: > 0.7
- `confidence`: > 0.8

### 2. Legitimate Traffic

**Test Event**: `tests/events/legitimate_event.json`

**Expected Results:**
- `is_fraud`: `false`
- `primary_fraud_type`: `legitimate`
- `ai_score`: < 0.3
- `confidence`: > 0.7

### 3. Borderline Cases

Test events with ML scores between 0.3 and 0.8 to verify AI analysis adds value.

## Troubleshooting

### Error: "on-demand throughput isn't supported"

**Solution:**
This means you need to use an inference profile instead of a direct model ID:

1. Go to AWS Bedrock Console → Inference → Inference profiles
2. Create a new inference profile
3. Add Claude 3.5 Sonnet model to the profile
4. Use the profile ID as `BEDROCK_MODEL_ID`

**Example:**
```bash
# Instead of:
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Use:
export BEDROCK_MODEL_ID=<your-inference-profile-id>
```

### Error: "Access Denied" or "Model not available"

**Solution:**
1. Check Bedrock model access in AWS Console
2. Verify IAM permissions include `bedrock:InvokeModel`
3. Ensure you're using the correct region (us-east-1)
4. Request model access if not already granted

### Error: "Invalid Model ID"

**Solution:**
1. Verify model ID or inference profile ID
2. Check if model/profile is available in your region
3. Try requesting model access again
4. Consider using an inference profile instead

### Error: "JSON Parse Error"

**Solution:**
- The AI analyzer has fallback parsing logic
- Check CloudWatch logs for the raw response
- The function should still return a valid response with low confidence

### Error: "Timeout"

**Solution:**
- Increase Lambda timeout (default is 30 seconds)
- Check Bedrock API latency
- Consider using Claude 3 Haiku for faster responses

### Error: "Module not found" (Local Testing)

**Solution:**
1. Ensure you're running from project root
2. Check Python path includes `src/ai_analyzer`
3. Install dependencies: `pip install -r scripts/test_bedrock_requirements.txt`

## Interpreting Results

### Success Metrics

1. **Success Rate**: Should be > 95% (most failures are due to AWS access issues)
2. **Fraud Detection Accuracy**: 
   - Fraud events should be detected as fraud
   - Legitimate events should be detected as legitimate
3. **Confidence Scores**: Should be > 0.7 for clear cases
4. **Response Time**: Should be < 3 seconds per analysis

### Response Structure

Each successful response should include:

```json
{
  "is_fraud": true,
  "confidence": 0.85,
  "ai_score": 0.87,
  "fraud_signals": ["bot_user_agent", "high_click_velocity", "datacenter_ip"],
  "reasoning": "This event shows clear signs of bot traffic...",
  "recommended_action": "block",
  "primary_fraud_type": "bot_traffic"
}
```

### Validation Checklist

- [ ] All required fields present (`is_fraud`, `confidence`, `ai_score`)
- [ ] Boolean values are actual booleans (not strings)
- [ ] Numeric values are numbers (not strings)
- [ ] `fraud_signals` is an array
- [ ] `reasoning` provides specific evidence
- [ ] `primary_fraud_type` matches expected fraud type

## Cost Monitoring

### Estimated Costs per Test

- **Input tokens**: ~500 tokens per prompt
- **Output tokens**: ~200 tokens per response
- **Cost per test**: ~$0.001 (less than 1 cent)

### Cost for 100 Tests

- Total cost: ~$0.10
- Input: 50k tokens × $3/1M = $0.15
- Output: 20k tokens × $15/1M = $0.30
- **Total: ~$0.45**

## Quick Start Checklist

1. ✅ Configure AWS credentials: `aws configure`
2. ✅ Request Bedrock model access in AWS Console
3. ✅ Create inference profile (if needed) and note the ID
4. ✅ Set environment variable: `export BEDROCK_MODEL_ID=<your-model-or-profile-id>`
5. ✅ Install dependencies: `pip install -r scripts/test_bedrock_requirements.txt`
6. ✅ Run test: `python scripts/test_bedrock_local.py --num-tests 2`
7. ✅ Verify results match expected output

## Next Steps

1. ✅ Run local tests to verify setup
2. ✅ Test with various fraud scenarios
3. ✅ Validate JSON output consistency
4. ✅ Monitor costs and performance
5. ✅ Integrate with decision combiner (Task 40)

## Additional Resources

- [Bedrock Setup Guide](src/ai_analyzer/BEDROCK_SETUP.md)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Claude 3.5 Sonnet Model Card](https://www.anthropic.com/claude)
- [Bedrock Inference Profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles.html)
