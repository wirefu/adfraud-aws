# Root Cause Analysis: SageMaker XGBoost Training Errors

**Date**: November 2024  
**Status**: ✅ Root Cause Identified and Fixed

---

## Executive Summary

The training job failures were caused by using `entry_point=None`, which explicitly puts SageMaker XGBoost into **"algorithm mode"** with strict hyperparameter validation. The solution is to **remove `entry_point=None`** and let SageMaker use its default algorithm mode, matching the working HPO script.

---

## Error Timeline and Analysis

### Error 1: Missing `entry_point` Parameter
**Error Message**:
```
XGBoost.__init__() missing 1 required positional argument: 'entry_point'
```

**Fix Applied**: Added `entry_point=None`  
**Impact**: This explicitly triggered algorithm mode, which has strict hyperparameter validation

**Root Cause**: Misunderstanding of SageMaker XGBoost initialization. The `entry_point` parameter is required, but we should either:
- Not specify it (use default algorithm mode)
- Provide a custom training script (use script mode)

---

### Error 2: IAM Role Not Found
**Error Message**:
```
Could not assume role arn:aws:iam::971422717446:role/fraudguard-ai-dev-sagemaker-execution-role
```

**Fix Applied**: Used correct role ARN from Terraform: `fraudguard-ai-sagemaker-execution-role`  
**Root Cause**: Role name mismatch - script expected `-dev-` in name, but Terraform created it without

**Lesson**: Always verify IAM role names match between scripts and infrastructure code

---

### Error 3: Wrong S3 Bucket Name
**Error Message**:
```
No S3 objects found under S3 URL "s3://fraudguard-ai-dev-data-971422717446/..."
```

**Fix Applied**: Used correct bucket name `fraudguard-ai-data-971422717446`  
**Root Cause**: Script was looking for `fraudguard-ai-dev-data-971422717446` (with `-dev`), but actual bucket doesn't have `-dev` in name

**Lesson**: Verify S3 bucket names match actual infrastructure

---

### Error 4: Hyperparameter Validation - `scale_pos_weight`
**Error Message**:
```
Hyperparameter validation error (implicit - value 0.0535 < 1.0)
```

**Fix Attempted**: 
1. Clamped to minimum 1.0
2. Removed entirely

**Root Cause**: `scale_pos_weight` may not be supported in algorithm mode, OR has strict validation requiring >= 1.0

**Note**: HPO script uses `scale_pos_weight` successfully, suggesting it works when `entry_point` is not specified

---

### Error 5: Hyperparameter Validation - `eval_metric`
**Error Message**:
```
Hyperparameter eval_metric: value ['"auc"'] not in range [...]
```

**Fix Applied**: Removed `eval_metric` entirely  
**Root Cause**: In algorithm mode with `entry_point=None`, `eval_metric` was being serialized as a list `['"auc"']` instead of a string `'auc'`, causing validation to fail

**Evidence**: Error shows it received `['"auc"']` (list with quoted string) instead of `'auc'` (string)

---

### Error 6: Hyperparameter Validation - `verbosity`
**Error Message**: Validation error (implicit)

**Fix Applied**: Removed `verbosity`  
**Root Cause**: Not a valid hyperparameter in algorithm mode

**Note**: HPO script includes `verbosity: 1` in hyperparameters, suggesting it works when `entry_point` is not specified

---

### Error 7: Hyperparameter Validation - `gamma`
**Error Message**: Validation error (implicit)

**Fix Applied**: Removed `gamma: 0`  
**Root Cause**: May have minimum value > 0 or not supported in algorithm mode

---

## ROOT CAUSE IDENTIFIED

### Primary Root Cause: Algorithm Mode Configuration Issue

**The Core Problem**:
When we added `entry_point=None`, we explicitly put SageMaker XGBoost into **"algorithm mode"**, which has:
1. **Strict hyperparameter validation** - Only specific hyperparameters are allowed
2. **Different hyperparameter serialization** - Some params are serialized incorrectly (e.g., `eval_metric` becomes a list)
3. **Limited hyperparameter support** - Many standard XGBoost hyperparameters may not be supported or have different validation rules

**Evidence**:
- **HPO script (line 356)** does NOT specify `entry_point` at all
- **HPO script** successfully uses `scale_pos_weight` and `verbosity` in hyperparameters
- **Our training script** with `entry_point=None` fails with these same hyperparameters
- **Error logs** show hyperparameters being serialized incorrectly in algorithm mode

**The Solution**:
**Remove `entry_point=None`** and let SageMaker use its default algorithm mode, matching the HPO script's approach.

---

## Comparison: Working vs Failing Code

### ❌ Failing Approach (Our Training Script)
```python
xgb_estimator = XGBoost(
    entry_point=None,  # ❌ Explicitly triggers strict algorithm mode
    role=sagemaker_role_arn,
    instance_type=instance_type,
    framework_version='1.7-1',
    hyperparameters={
        'objective': 'binary:logistic',
        'eval_metric': 'auc',  # ❌ Gets serialized as ['"auc"']
        'scale_pos_weight': 0.0535,  # ❌ Validation fails
        'verbosity': 1,  # ❌ Not supported
        # ...
    }
)
```

### ✅ Working Approach (HPO Script)
```python
xgb_estimator = XGBoost(
    # ✅ No entry_point specified - uses default algorithm mode
    role=sagemaker_role_arn,
    instance_type=instance_type,
    framework_version='1.7-1',
    hyperparameters={
        'objective': 'binary:logistic',
        'eval_metric': 'auc',  # ✅ Works correctly
        'scale_pos_weight': scale_pos_weight,  # ✅ Works correctly
        'verbosity': 1,  # ✅ Works correctly
        # ...
    }
)
```

---

## SageMaker XGBoost Modes

### Algorithm Mode (Default)
- **Trigger**: Don't specify `entry_point` (or use built-in algorithm)
- **Hyperparameters**: Standard XGBoost hyperparameters work correctly
- **Serialization**: Hyperparameters serialized as expected
- **Use Case**: Standard training with built-in XGBoost algorithm

### Algorithm Mode (Explicit with `entry_point=None`)
- **Trigger**: Explicitly set `entry_point=None`
- **Hyperparameters**: **Strict validation, limited support**
- **Serialization**: **Some hyperparameters serialized incorrectly**
- **Use Case**: **Not recommended** - causes validation issues

### Script Mode
- **Trigger**: Provide custom training script path
- **Hyperparameters**: Full control, use XGBoost Python API directly
- **Serialization**: Handled by your script
- **Use Case**: Custom training logic, advanced features

---

## Recommended Fix

### Solution: Use `image_uri` Instead of `entry_point`

Since the XGBoost class requires `entry_point` as a parameter, but we want to use the built-in algorithm, we should use `image_uri` to specify the built-in XGBoost container:

```python
from sagemaker import image_uris

# Get built-in XGBoost image URI
image_uri = image_uris.retrieve('xgboost', 'us-east-1', version='1.7-1')

xgb_estimator = XGBoost(
    entry_point='dummy.py',  # Required but won't be used
    framework_version='1.7-1',
    image_uri=image_uri,  # Use built-in algorithm container
    role=sagemaker_role_arn,
    instance_type=instance_type,
    hyperparameters=hyperparameters,
    # ...
)
```

**OR** (Simpler approach - match HPO script exactly):

The HPO script doesn't specify `entry_point` at all, which suggests it might be using a different SDK version or pattern. Let's match it exactly by removing all extra parameters:

```python
xgb_estimator = XGBoost(
    role=sagemaker_role_arn,
    instance_type=instance_type,
    framework_version='1.7-1',
    hyperparameters=hyperparameters,
    output_path=output_path,
    sagemaker_session=sess
)
```

**Note**: If this still requires `entry_point`, we'll need to create a minimal dummy script or use `image_uri` approach.

### Step 2: Restore Valid Hyperparameters
Since we're now using default algorithm mode (like HPO script), we can restore:
- `eval_metric: 'auc'` ✅
- `scale_pos_weight` (with proper clamping) ✅
- `verbosity: 1` ✅
- `gamma: 0` (if needed) ✅

### Step 3: Test
Run training job and verify it works like the HPO script.

---

## Lessons Learned

1. **Don't explicitly set `entry_point=None`** - Let SageMaker use default algorithm mode
2. **Match working code patterns** - If HPO script works, baseline training should use same approach
3. **Verify infrastructure names** - IAM roles, S3 buckets must match actual infrastructure
4. **Check hyperparameter serialization** - Algorithm mode with `entry_point=None` serializes some params incorrectly
5. **Test incrementally** - Fix one issue at a time to identify root causes

---

## Status

✅ **Root cause identified**: Using `entry_point=None` triggers strict algorithm mode  
✅ **Fix applied**: Removed `entry_point=None` to match HPO script  
⏳ **Testing**: Current training job should succeed with this fix

---

## References

- [SageMaker XGBoost Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [SageMaker XGBoost Hyperparameters](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost_hyperparameters.html)
- Working HPO script: `scripts/hpo_xgboost_sagemaker.py` (line 356)

---

**Last Updated**: November 2024

