# Terraform IAM Permission Fix - Complete ✅

## Date: 2025-11-14

---

## Issue

Lambda orchestrator (`fraudguard-ai-orchestrator-dev`) was unable to invoke SageMaker endpoint due to missing IAM permission.

**Error**:
```
AccessDeniedException: User is not authorized to perform: 
sagemaker:InvokeEndpoint
```

---

## Solution: Terraform Deployment

### Step 1: Created Terraform Configuration

**File**: `terraform/lambda_sagemaker_iam.tf`

```hcl
resource "aws_iam_role_policy" "orchestrator_sagemaker_invoke" {
  name = "SageMakerInvokeEndpointPolicy"
  role = "fraudguard-ai-lambda-execution-role-dev"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sagemaker:InvokeEndpoint"
        Resource = "arn:aws:sagemaker:us-east-1:971422717446:endpoint/*"
      }
    ]
  })
}
```

### Step 2: Imported Existing Policy

Since the policy was manually added earlier, we imported it into Terraform state:

```bash
terraform import aws_iam_role_policy.orchestrator_sagemaker_invoke \
  fraudguard-ai-lambda-execution-role-dev:SageMakerInvokeEndpointPolicy
```

### Step 3: Applied Configuration

```bash
cd terraform
terraform plan
terraform apply
```

**Result**: ✅ Policy now managed by Terraform

---

## Verification

### Test Results

**Before Fix**:
- Lambda returned fallback score: `0.5`
- Error in logs: `AccessDeniedException`

**After Fix**:
- Lambda calls SageMaker directly: ✅
- ML Score: `0.5642` (from SageMaker, not fallback)
- No errors in logs: ✅

### Multiple Test Events

All test events now receive scores from SageMaker (not fallback):
- Test 1: `0.5642` ✅
- Test 2: `0.5642` ✅
- Test 3: `0.5642` ✅

---

## Terraform State

The IAM policy is now managed by Terraform:

```bash
cd terraform
terraform show aws_iam_role_policy.orchestrator_sagemaker_invoke
```

**Resource ID**: `fraudguard-ai-lambda-execution-role-dev:SageMakerInvokeEndpointPolicy`

---

## Benefits of Terraform Management

1. **Version Control**: Policy changes tracked in Git
2. **Reproducibility**: Can recreate in any environment
3. **State Management**: Terraform tracks policy state
4. **Team Collaboration**: Changes reviewed via PRs
5. **Infrastructure as Code**: Policy defined declaratively

---

## Future Updates

To modify the policy:

1. Edit `terraform/lambda_sagemaker_iam.tf`
2. Run `terraform plan` to preview changes
3. Run `terraform apply` to deploy

Example: To allow multiple endpoints:
```hcl
Resource = "arn:aws:sagemaker:us-east-1:971422717446:endpoint/*"
```

---

## Summary

| Component | Status | Method |
|-----------|--------|--------|
| IAM Policy | ✅ Deployed | Terraform |
| Lambda Integration | ✅ Working | Calling SageMaker directly |
| ML Scores | ✅ Real | Not using fallback |
| Terraform State | ✅ Managed | Policy in state |

**Overall**: ✅ **COMPLETE - IAM permissions fixed and managed by Terraform**

---

## Next Steps

1. ✅ IAM permissions fixed
2. ✅ Terraform managing policy
3. ✅ Lambda calling SageMaker directly
4. ⏳ Monitor production performance
5. ⏳ Set up CloudWatch dashboards

---

## References

- **Terraform File**: `terraform/lambda_sagemaker_iam.tf`
- **Integration Test Results**: `docs/COMPLETE_TEST_RESULTS.md`
- **Terraform Guide**: `docs/TERRAFORM_DEPLOYMENT.md`

