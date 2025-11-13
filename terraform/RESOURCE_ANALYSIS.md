# Resource Reuse Analysis for Terraform Migration

## ✅ EXISTING RESOURCES (Can Be Reused - Import into Terraform)

### 1. DynamoDB Table
- **Name**: `fraudguard-events-dev`
- **Status**: ACTIVE
- **Current GSIs**: 
  - ✅ `campaign-timestamp-index` (campaign_id + timestamp)
  - ✅ `device-timestamp-index` (device_id + timestamp)
- **Missing GSIs** (need to be added):
  - ❌ `gclid-timestamp-index` (gclid + timestamp)
  - ❌ `keyword-timestamp-index` (keyword + timestamp)
  - ❌ `target-timestamp-index` (target_id + timestamp)
- **Missing Attributes** (need to be added):
  - ❌ `gclid` (String)
  - ❌ `keyword` (String)
  - ❌ `target_id` (String)
- **Action**: 
  - ✅ REUSE existing table
  - ⚠️ ADD missing attributes and GSIs (cannot add attributes after table creation, but GSIs can reference existing attributes if they exist in items)

### 2. S3 Bucket
- **Name**: `fraudguard-ai-data-971422717446`
- **Status**: EXISTS (already imported to Terraform)
- **Action**: ✅ REUSE (already done)

### 3. Lambda Functions (Core - Without -dev suffix)
- ✅ `fraudguard-ai-ingestion-handler` - EXISTS
- ✅ `fraudguard-ai-orchestrator` - EXISTS
- ✅ `fraudguard-ai-ai-analyzer` - EXISTS
- ✅ `fraudguard-ai-decision-combiner` - EXISTS
- ✅ `fraudguard-ai-honeypot` - EXISTS
- **Action**: ✅ REUSE (import into Terraform state)

### 4. IAM Roles (Individual per Lambda)
- ✅ `fraudguard-ai-IngestionHandlerRole-znlfQeLxomxF`
- ✅ `fraudguard-ai-FraudOrchestratorRole-oFPS99y2YsLm`
- ✅ `fraudguard-ai-AIAnalyzerRole-5MQCC15u0aa6`
- ✅ `fraudguard-ai-DecisionCombinerRole-pbRjQV8V0IUn`
- ✅ `fraudguard-ai-HoneypotFunctionRole-qd95QAiF1c4F`
- **Action**: ✅ REUSE (import into Terraform state)

### 5. API Gateway
- ✅ Honeypot API (`h6vf8d68rg`) - EXISTS
- **Action**: ✅ REUSE (if needed for Terraform management)

## ❌ DUPLICATE RESOURCES (Created by Terraform - Should Be Removed)

### 1. DynamoDB Table
- **Name**: `fraudguard-ai-events-dev`
- **Created**: By Terraform (just now)
- **Action**: ❌ DELETE (use existing `fraudguard-events-dev` instead)
- **Reason**: Duplicate table, existing one is already in use

### 2. Lambda Functions (With -dev suffix)
- ❌ `fraudguard-ai-ingestion-handler-dev` - DUPLICATE
- ❌ `fraudguard-ai-orchestrator-dev` - DUPLICATE
- ❌ `fraudguard-ai-ai-analyzer-dev` - DUPLICATE
- ❌ `fraudguard-ai-decision-combiner-dev` - DUPLICATE
- **Action**: ❌ DELETE (use existing functions without -dev suffix)
- **Reason**: Core functions already exist and are in use

### 3. IAM Role
- ❌ `fraudguard-ai-lambda-execution-role-dev` - DUPLICATE
- **Action**: ❌ DELETE (use existing individual roles per Lambda)
- **Reason**: CloudFormation uses individual roles per function, not a shared role

## 🔍 RESOURCES THAT NEED CREATION

### 1. Missing DynamoDB GSIs (Add to existing table)
- ⚠️ `gclid-timestamp-index` - NEEDS CREATION
  - **Why**: Required for Google Ads GCLID lookups
  - **Note**: Requires `gclid` attribute to exist in table items
- ⚠️ `keyword-timestamp-index` - NEEDS CREATION
  - **Why**: Required for keyword-based queries
  - **Note**: Requires `keyword` attribute to exist in table items
- ⚠️ `target-timestamp-index` - NEEDS CREATION
  - **Why**: Required for target/placement-based queries
  - **Note**: Requires `target_id` attribute to exist in table items

**Important**: DynamoDB cannot add new attributes to AttributeDefinitions after table creation, but GSIs can be added if the attributes already exist in items. The attributes (gclid, keyword, target_id) may already be in use in items even if not in AttributeDefinitions.

## 📋 RECOMMENDED ACTION PLAN

1. **Import existing resources into Terraform state**:
   - DynamoDB table: `fraudguard-events-dev`
   - Lambda functions (without -dev suffix)
   - IAM roles (individual roles)
   - S3 bucket (already done)

2. **Remove duplicate resources**:
   - Delete `fraudguard-ai-events-dev` DynamoDB table
   - Delete Lambda functions with `-dev` suffix
   - Delete shared IAM role

3. **Add missing GSIs to existing table**:
   - Add `gclid-timestamp-index`
   - Add `keyword-timestamp-index`
   - Add `target-timestamp-index`

4. **Update Terraform configuration**:
   - Use data sources or imported resources instead of creating new ones
   - Reference existing Lambda functions
   - Reference existing IAM roles
