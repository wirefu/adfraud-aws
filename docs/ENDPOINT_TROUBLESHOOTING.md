# SageMaker Endpoint Troubleshooting

## Issue: Endpoint Returns Empty Array `[]`

If your SageMaker endpoint returns `[]` instead of a prediction score, this indicates a deployment or model configuration issue.

### Possible Causes

1. **Model Artifact Issue**: The model file may not be properly packaged or uploaded
2. **Container Configuration**: The XGBoost container may not be configured correctly
3. **Input Format Mismatch**: The model expects a different input format than what's being sent

### Diagnostic Steps

1. **Check Endpoint Status**:
```bash
aws sagemaker describe-endpoint \
    --endpoint-name fraudguard-xgboost-endpoint \
    --query 'EndpointStatus' \
    --output text
```

2. **Check Endpoint Logs**:
```bash
aws logs tail /aws/sagemaker/Endpoints/fraudguard-xgboost-endpoint --follow
```

3. **Check Model Configuration**:
```bash
aws sagemaker describe-model \
    --model-name fraudguard-xgboost-model \
    --query '{ModelName:ModelName,PrimaryContainer:PrimaryContainer}' \
    --output json
```

### Solution: Redeploy with Proper Configuration

The endpoint needs to be deployed with CSV serializer/deserializer. Check the deployment script:

```python
from sagemaker.xgboost.model import XGBoostModel
from sagemaker.serializers import CSVSerializer
from sagemaker.deserializers import CSVDeserializer

model = XGBoostModel(
    model_data=model_s3_path,
    role=sagemaker_role_arn,
    framework_version='1.7-1',
    py_version='py3',
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',
    endpoint_name='fraudguard-xgboost-endpoint',
    serializer=CSVSerializer(),      # ✅ Required
    deserializer=CSVDeserializer()     # ✅ Required
)
```

### Alternative: Use boto3 with Proper Content Type

If the endpoint was deployed without serializer/deserializer, you may need to specify the Accept header:

```python
import boto3

runtime = boto3.client('sagemaker-runtime')

response = runtime.invoke_endpoint(
    EndpointName='fraudguard-xgboost-endpoint',
    ContentType='text/csv',
    Accept='text/csv',  # ✅ Add this
    Body=features_csv
)
```

### Next Steps

1. Check the deployment script used to create the endpoint
2. Verify the model artifact is correct
3. Consider redeploying with the proper configuration
4. Test with a simple feature vector first

