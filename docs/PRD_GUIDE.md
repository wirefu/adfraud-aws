# PRD Guide: Which Document to Use

**Date**: November 2024

---

## Overview

This project has multiple PRDs and guides. Here's which one to use for different tasks:

---

## Primary PRDs

### 1. **`docs/ad-fraud-detection-prd.md`** - Main Product PRD

**Use this for**:
- Understanding the overall system architecture
- Product requirements and features
- ML model specifications (high-level)
- System design and components
- CI/CD pipeline requirements
- Overall project scope

**When to reference**:
- Starting a new feature
- Understanding system architecture
- Product planning
- High-level requirements

**Key Sections**:
- Problem statement
- Solution overview
- System architecture
- ML model requirements (high-level)
- Deployment strategy

---

### 2. **`docs/DATA_TRAINING_PRD.md`** - Data Training PRD ⭐ **USE THIS FOR TRAINING**

**Use this for**:
- **Training data preparation** (TalkingData, FDB, synthetic)
- **Feature engineering** requirements
- **Model training** specifications (XGBoost)
- **SageMaker** configuration
- **Hyperparameter optimization** (HPO)
- **Model deployment** to SageMaker endpoint
- **AWS infrastructure** for training
- **Multi-platform** feature support

**When to reference**:
- ✅ **Processing training data**
- ✅ **Training the XGBoost model**
- ✅ **Setting up SageMaker**
- ✅ **Feature engineering**
- ✅ **Model evaluation**
- ✅ **Deployment to endpoint**

**Key Sections**:
- Data sources (TalkingData, FDB, synthetic)
- Feature engineering requirements (20+ features)
- Model training specifications
- SageMaker configuration
- AWS infrastructure
- Implementation plan

---

## Supporting Guides

### 3. **`docs/TRAINING_START_GUIDE.md`** - Step-by-Step Training Guide

**Use this for**:
- **Quick start** steps to begin training
- **Immediate actions** checklist
- **Command examples**
- **Troubleshooting** common issues

**When to reference**:
- Starting training for the first time
- Need step-by-step instructions
- Quick command reference

---

### 4. **`docs/XGBOOST_TRAINING_GUIDE.md`** - XGBoost Technical Guide

**Use this for**:
- XGBoost-specific training details
- Hyperparameter tuning
- Class imbalance handling
- Evaluation metrics
- SageMaker XGBoost algorithm details

**When to reference**:
- Configuring XGBoost hyperparameters
- Understanding class imbalance solutions
- Model evaluation metrics

---

### 5. **`docs/MULTI_PLATFORM_ARCHITECTURE.md`** - Multi-Platform Guide

**Use this for**:
- Understanding platform abstraction
- Google Ads, Meta Ads, LinkedIn Ads support
- Platform-specific features
- Adding new platforms

**When to reference**:
- Working with multi-platform features
- Adding new ad platform support
- Understanding platform adapters

---

## Quick Decision Tree

### "I want to train the fraud detection model"

→ **Use `docs/DATA_TRAINING_PRD.md`** (Primary)
→ **Also reference `docs/TRAINING_START_GUIDE.md`** (Step-by-step)
→ **Also reference `docs/XGBOOST_TRAINING_GUIDE.md`** (Technical details)

### "I want to understand the overall system"

→ **Use `docs/ad-fraud-detection-prd.md`** (Main PRD)

### "I want to add a new ad platform"

→ **Use `docs/MULTI_PLATFORM_ARCHITECTURE.md`**

### "I want to deploy infrastructure"

→ **Use `docs/TERRAFORM_DEPLOYMENT.md`** (Terraform)
→ **Or `template.yaml`** (CloudFormation/SAM)

---

## For Your Current Task: Processing and Training

**Primary Document**: `docs/DATA_TRAINING_PRD.md`

**Why**:
- Contains all training data requirements
- Feature engineering specifications
- SageMaker configuration details
- AWS infrastructure requirements
- Implementation plan with phases
- Cost estimates
- Success criteria

**Supporting Documents**:
1. `docs/TRAINING_START_GUIDE.md` - For step-by-step commands
2. `docs/XGBOOST_TRAINING_GUIDE.md` - For XGBoost technical details
3. `docs/MULTI_PLATFORM_ARCHITECTURE.md` - For multi-platform features

---

## Document Relationships

```
┌─────────────────────────────────────────────────────────┐
│         ad-fraud-detection-prd.md (Main PRD)            │
│         - Overall system architecture                    │
│         - Product requirements                           │
│         - High-level ML specs                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ├──► DATA_TRAINING_PRD.md (Training PRD)
                   │    - Detailed training requirements
                   │    - Data preparation
                   │    - Model training specs
                   │    - AWS infrastructure
                   │
                   ├──► MULTI_PLATFORM_ARCHITECTURE.md
                   │    - Platform abstraction
                   │    - Multi-platform support
                   │
                   └──► TERRAFORM_DEPLOYMENT.md
                        - Infrastructure deployment
```

---

## Recommended Reading Order

### For Training Work:

1. **Start**: `docs/DATA_TRAINING_PRD.md` - Section 1 (Executive Summary)
2. **Data**: `docs/DATA_TRAINING_PRD.md` - Section 2 (Data Sources)
3. **Features**: `docs/DATA_TRAINING_PRD.md` - Section 3.3 (Feature Engineering)
4. **Training**: `docs/DATA_TRAINING_PRD.md` - Section 4 (Model Training)
5. **Steps**: `docs/TRAINING_START_GUIDE.md` - For implementation steps
6. **Technical**: `docs/XGBOOST_TRAINING_GUIDE.md` - For XGBoost details

---

## Summary

**For processing and training fraud data, use**:

✅ **`docs/DATA_TRAINING_PRD.md`** - Your primary reference  
✅ **`docs/TRAINING_START_GUIDE.md`** - For step-by-step actions  
✅ **`docs/XGBOOST_TRAINING_GUIDE.md`** - For technical details  

The main PRD (`ad-fraud-detection-prd.md`) is for overall system understanding, but the **DATA_TRAINING_PRD.md** is specifically designed for your training task.

