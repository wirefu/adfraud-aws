# Product Requirements Document: AI-Powered Ad Fraud Detection System

**Document Version:** 1.0  
**Date:** November 5, 2025  
**Author:** Lumina  
**Status:** Draft - Prototype/PoC  
**Project Code Name:** FraudGuard AI

---

## Executive Summary

FraudGuard AI is an intelligent ad fraud detection system that combines traditional machine learning with advanced AI analysis to identify and block fraudulent advertising traffic in real-time. The system uses a two-tier detection approach: fast ML-based screening (XGBoost) for immediate decisions, augmented by AI-powered deep analysis (Amazon Bedrock/Claude) for sophisticated fraud patterns that traditional models might miss.

**Target:** Prototype with automated CI/CD pipeline  
**Timeline:** 3 weeks from kickoff to demo  
**Deployment:** Automated CI/CD pipeline with GitHub Actions, dev environment only

---

## 1. Problem Statement

### The Problem
Digital advertising fraud costs the industry an estimated $100 billion annually. Current fraud detection solutions face several challenges:
- **False negatives:** Sophisticated bot networks evade rule-based and traditional ML detection
- **False positives:** Legitimate users blocked, causing revenue loss
- **Lack of explainability:** Black-box models can't explain why traffic was flagged
- **Latency:** Slow detection leads to wasted ad spend
- **Evolving tactics:** Fraudsters constantly adapt, outpacing static detection rules

### Our Solution
An AI-augmented fraud detection system that:
- Detects 95%+ of fraud patterns in <100ms (ML layer)
- Analyzes complex behavioral patterns using LLMs (AI layer)
- Provides human-readable explanations for every fraud decision
- Adapts to new fraud tactics through continuous learning
- Reduces false positives by 40% compared to ML-only approaches

---

---

## 4. CI/CD Pipeline & Deployment Strategy

### 4.1 Environment Strategy

**Single Development Environment:**

For this prototype phase, we'll focus on a **single development environment** with automated CI/CD deployment. This provides:
- Fast iteration cycles
- Automated testing and deployment
- Infrastructure as Code
- CI/CD best practices
- Foundation for adding more environments later

| Environment | Purpose | Deploy Trigger | Approval Required |
|-------------|---------|----------------|-------------------|
| **Development** | Feature development, testing, demo | Auto on push to `main` branch | No |

**Why Dev Only for Prototype:**
- Faster development cycle (no multi-environment coordination)
- Lower costs during prototype phase
- Simpler CI/CD pipeline to set up
- Can easily add staging/prod later when needed
- Sufficient for demo and technical validation

**Post-Prototype:** Once validated, we can extend the pipeline to include staging and production environments using the same SAM templates and GitHub Actions workflows.

### 4.2 GitHub Actions Workflow

#### Main Deployment Workflow (Simplified for Dev)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Dev

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:  # Manual trigger

jobs:
  # JOB 1: Code Quality & Security
  lint-and-scan:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Run pylint, flake8, black
      - Run bandit (security scan)
      - Run safety check (dependency vulnerabilities)
  
  # JOB 2: Unit Tests
  test:
    runs-on: ubuntu-latest
    steps:
      - Run pytest with coverage
      - Upload coverage to CodeCov
      - Fail if coverage < 80%
  
  # JOB 3: Build
  build:
    needs: [lint-and-scan, test]
    runs-on: ubuntu-latest
    steps:
      - SAM build
      - SAM validate
      - Upload artifacts
  
  # JOB 4: Deploy to Dev
  deploy-dev:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - SAM deploy to dev
      - Run smoke tests
      - Notify team (Slack/Email)
```

#### Pull Request Workflow

```yaml
# .github/workflows/pr-checks.yml
name: Pull Request Checks

on:
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - Code quality checks
      - Unit tests
      - Integration tests
      - SAM validate
      - Security scan
      - Comment PR with results
```

**Simplified Flow:**
1. Developer pushes to feature branch
2. Opens PR to `main`
3. GitHub Actions runs tests and checks
4. Team reviews and approves
5. Merge to `main` → auto-deploy to dev
6. Smoke tests verify deployment
7. Team notified of successful deployment

### 4.3 Deployment Process

#### Feature Development Flow (Simplified)

```
1. Developer creates feature branch: `feature/add-fraud-signal`
2. Makes changes to code
3. Commits and pushes to GitHub
4. Opens Pull Request to `main` branch
5. GitHub Actions runs:
   - Lint/format checks
   - Unit tests
   - Security scans
6. Code review by team member
7. Merge to `main` branch
8. Auto-deploys to DEV environment
9. Smoke tests run automatically
10. Team gets notification
11. Test in dev environment
12. Ready for demo!
```

#### Hotfix Flow

```
1. Create hotfix branch from `main`: `hotfix/critical-bug`
2. Make fix
3. Open PR to `main` (expedited review)
4. Merge to `main`
5. Auto-deploy to DEV
6. Quick validation
```

**Note:** Since this is a prototype with a single environment, the deployment process is streamlined. Post-prototype, we can easily add staging and production environments with approval gates.

### 4.4 Infrastructure as Code

**SAM Template Structure:**
```
template.yaml              # Main infrastructure
├── Parameters             # Environment-specific settings
├── Conditions             # Environment-based logic
├── Resources
│   ├── API Gateway
│   ├── Lambda Functions (5 total)
│   ├── DynamoDB Table
│   ├── S3 Buckets
│   ├── IAM Roles & Policies
│   ├── CloudWatch Alarms
│   └── X-Ray Tracing
└── Outputs                # API URLs, resource names
```

**Parameter Configuration:**
```bash
# Dev deployment (single environment)
sam deploy --parameter-overrides \
  Environment=dev \
  SageMakerEndpointName=fraud-xgboost-dev \
  ApiThrottleRate=500
```

**Future:** When adding staging/prod, simply update the parameter values:
```bash
# Staging (future)
Environment=staging SageMakerEndpointName=fraud-xgboost-staging ApiThrottleRate=1000

# Production (future)
Environment=prod SageMakerEndpointName=fraud-xgboost-prod ApiThrottleRate=2000
```

### 4.5 Testing Strategy in CI/CD

#### Unit Tests (Runs on every commit)
```python
# tests/unit/test_ingest_handler.py
def test_ingest_valid_event():
    """Test ingestion with valid ad event"""
    event = create_valid_api_event()
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200

def test_ingest_missing_field():
    """Test ingestion with missing required field"""
    event = create_invalid_api_event()
    response = lambda_handler(event, None)
    assert response['statusCode'] == 400
```

**Coverage Requirement:** 80% minimum

#### Integration Tests (Runs in staging)
```python
# tests/integration/test_fraud_detection_flow.py
def test_end_to_end_fraud_detection():
    """Test complete fraud detection flow"""
    # 1. Send fraud event to API
    response = requests.post(API_URL, json=fraud_event)
    
    # 2. Verify immediate response
    assert response.status_code == 200
    assert 'fraud_score' in response.json()
    
    # 3. Verify DynamoDB storage
    item = dynamodb.get_item(event_id)
    assert item['is_fraud'] == True
    
    # 4. Verify S3 storage
    assert s3_object_exists(event_id)
```

#### Load Tests (Runs in staging before prod deploy)
```python
# tests/load/locustfile.py
class FraudDetectionUser(HttpUser):
    @task
    def detect_fraud(self):
        self.client.post("/v1/detect-fraud", json=generate_event())

# Run: locust -f locustfile.py --users 1000 --spawn-rate 100
```

**Load Test Targets:**
- 1000 concurrent users
- 500 req/sec sustained for 10 minutes
- P95 latency < 150ms (ML path)
- P95 latency < 3500ms (AI path)
- 0% error rate

#### Smoke Tests (Runs after every deployment)
```python
# tests/smoke/test_health.py
def test_api_health():
    """Verify API is responding"""
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200

def test_fraud_detection_basic():
    """Verify basic fraud detection works"""
    response = requests.post(
        f"{API_URL}/v1/detect-fraud",
        json=create_test_event()
    )
    assert response.status_code == 200
    assert 'fraud_score' in response.json()
```

### 4.6 Rollback Strategy

**Automated Rollback Triggers:**
- Error rate > 5% for 5 minutes
- P95 latency > 5000ms for 5 minutes
- Any Lambda function throttling

**Rollback Process:**
```bash
# Option 1: CloudFormation rollback (automatic)
# If deployment fails, SAM automatically rolls back

# Option 2: Manual rollback to previous version
sam deploy --parameter-overrides \
  Environment=prod \
  --no-confirm-changeset \
  --stack-name fraud-detection-prod-rollback

# Option 3: Specific Lambda rollback
aws lambda update-function-code \
  --function-name prod-fraud-detection-ingest \
  --s3-bucket sam-artifacts \
  --s3-key previous-version.zip
```

### 4.7 Secrets Management

**GitHub Secrets (Required):**
```
AWS_ACCESS_KEY_ID           # AWS credentials for deployment
AWS_SECRET_ACCESS_KEY       # AWS credentials
AWS_REGION                  # us-east-1
SAGEMAKER_ENDPOINT_DEV      # SageMaker endpoint names
SAGEMAKER_ENDPOINT_STAGING
SAGEMAKER_ENDPOINT_PROD
SLACK_WEBHOOK_URL           # For deployment notifications
CODECOV_TOKEN               # For coverage reporting
```

**AWS Secrets Manager (Application Secrets):**
```
/fraud-detection/dev/api-keys        # API keys for dev
/fraud-detection/staging/api-keys    # API keys for staging  
/fraud-detection/prod/api-keys       # API keys for production
/fraud-detection/prod/bedrock-config # Bedrock configuration
```

### 4.8 Monitoring & Alerting

**CloudWatch Alarms (Auto-created by SAM):**
- API Gateway 5XX errors > 10 in 5 minutes
- Lambda errors > 5 in 5 minutes
- Lambda duration > p95 threshold
- DynamoDB throttling events
- SageMaker endpoint failures

**Custom Metrics:**
```python
# In Lambda code
from aws_lambda_powertools import Metrics
metrics = Metrics(namespace="FraudDetection")

metrics.add_metric(name="FraudDetected", unit="Count", value=1)
metrics.add_metric(name="FraudScore", unit="None", value=fraud_score)
```

**Dashboard:**
- Real-time fraud rate
- API latency (p50, p95, p99)
- Error rates by function
- Cost per 10k events
- ML vs AI usage ratio

### 4.9 Cost Management

**Budget Alerts:**
```yaml
# AWS Budget configured via SAM
Budgets:
  DevBudget:
    Amount: 500
    Period: Monthly
    Alert: 80% threshold
  
  StagingBudget:
    Amount: 800
    Period: Monthly
    Alert: 80% threshold
  
  ProductionBudget:
    Amount: 2000
    Period: Monthly
    Alert: 80% threshold
```

**Cost Optimization in CI/CD:**
- Dev environment auto-shuts down Lambda after 1 hour idle
- Staging uses smaller SageMaker instance (ml.t2.medium vs ml.m5.large)
- Production uses auto-scaling with min/max capacity
- All environments use DynamoDB on-demand (no over-provisioning)

### 4.10 Documentation & Runbooks

**Auto-generated Documentation:**
- API documentation (OpenAPI/Swagger) generated from SAM template
- Architecture diagrams updated on each deployment
- Deployment history tracked in GitHub releases

**Runbooks:**
1. **Deployment Runbook** - Step-by-step deployment guide
2. **Rollback Runbook** - Emergency rollback procedures
3. **Troubleshooting Guide** - Common issues and fixes
4. **Disaster Recovery** - Backup/restore procedures

---

## 5. Goals & Success Metrics

### Primary Goals
1. **Demonstrate technical feasibility** of AI-augmented fraud detection
2. **Achieve >90% fraud detection accuracy** on benchmark datasets
3. **Maintain <3 second end-to-end latency** for AI-analyzed events
4. **Generate explainable fraud reports** that non-technical stakeholders can understand

### Success Metrics (Prototype Phase)

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Fraud Detection Rate | >90% | Testing on labeled fraud dataset |
| False Positive Rate | <5% | Testing on legitimate traffic dataset |
| ML Latency (Tier 1) | <100ms | CloudWatch metrics |
| AI Latency (Tier 2) | <3s | CloudWatch metrics |
| ML+AI Accuracy vs ML-only | +10-15% | A/B comparison on test set |
| System Uptime | >99% | CloudWatch monitoring |
| Cost per 10k events analyzed | <$5 | AWS Cost Explorer |

### Business Outcomes (Post-Prototype)
- **ROI:** 10:1 (save $10 in fraud for every $1 spent on detection)
- **Customer adoption:** 3-5 pilot customers within 3 months of launch
- **Market validation:** Positive feedback from 80%+ of demo attendees

---

## 3. Target Users & Use Cases

### Primary Users
1. **Digital Advertisers** - Protect ad budgets from click fraud
2. **Ad Networks** - Maintain platform quality and advertiser trust
3. **Ad Verification Companies** - Enhance existing fraud detection capabilities
4. **Marketing Teams** - Optimize campaign performance by eliminating fraud

### Use Cases

#### Use Case 1: Real-Time Click Fraud Detection
**Actor:** Ad Network Platform  
**Goal:** Block fraudulent clicks before charging advertisers  
**Flow:**
1. Ad click event arrives via API
2. System analyzes in real-time (<100ms)
3. Obvious fraud blocked immediately (ML Tier 1)
4. Borderline cases analyzed by AI (Tier 2, <3s)
5. Decision + explanation returned to platform

#### Use Case 2: Campaign Fraud Analysis
**Actor:** Digital Advertiser  
**Goal:** Understand if campaign is under fraud attack  
**Flow:**
1. Advertiser views campaign dashboard
2. System shows fraud rate trends over time
3. AI provides natural language explanation of fraud patterns
4. Actionable recommendations displayed (e.g., "Block traffic from IP range X")

#### Use Case 3: Post-Campaign Fraud Audit
**Actor:** Ad Verification Company  
**Goal:** Generate comprehensive fraud report for client  
**Flow:**
1. Upload batch of ad event data
2. System processes all events (ML + AI)
3. Generate detailed PDF report with:
   - Overall fraud percentage
   - Fraud breakdown by type (bots, click farms, etc.)
   - Geographic fraud hotspots
   - AI-generated insights and recommendations

---

## 4. Technical Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│              Ad Event Source (Client)                │
│         (Website, Mobile App, Ad Network)            │
└────────────────────┬────────────────────────────────┘
                     │ HTTPS POST
                     ↓
┌─────────────────────────────────────────────────────┐
│              AWS API Gateway                         │
│         • REST API endpoint                          │
│         • Request validation                         │
│         • Rate limiting (10k req/sec)                │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│         Lambda: Ingestion Handler                    │
│         • Parse ad event                             │
│         • Enrich with context (DynamoDB lookups)     │
│         • Store raw event (S3 + DynamoDB)            │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│         Lambda: Fraud Orchestrator                   │
│         • Route to ML or ML+AI path                  │
└───────┬─────────────────────────────┬───────────────┘
        │                             │
        ↓                             ↓
┌──────────────────┐         ┌───────────────────────┐
│  TIER 1: ML      │         │  TIER 2: AI           │
│  Fast Screening  │         │  Deep Analysis        │
│                  │         │                       │
│  SageMaker       │         │  Amazon Bedrock       │
│  XGBoost         │         │  Claude 3 Sonnet      │
│  Endpoint        │         │                       │
│                  │         │  • Pattern analysis   │
│  <100ms          │         │  • Explainability     │
│  90% of traffic  │         │  • Sophisticated      │
│                  │         │    fraud detection    │
│                  │         │                       │
│                  │         │  1-3s, 10% traffic    │
└────────┬─────────┘         └───────────┬───────────┘
         │                               │
         └───────────────┬───────────────┘
                         │
                         ↓
              ┌──────────────────────┐
              │  Decision Combiner    │
              │  • Ensemble scoring   │
              │  • Final verdict      │
              └──────────┬────────────┘
                         │
         ┌───────────────┼───────────────┐
         ↓               ↓               ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  DynamoDB   │  │     S3      │  │ CloudWatch  │
│  • Events   │  │  • Raw data │  │  • Metrics  │
│  • Results  │  │  • Training │  │  • Logs     │
└─────────────┘  └─────────────┘  └─────────────┘
         │
         ↓
┌─────────────────────────────────────────────────────┐
│         Dashboard (Streamlit on App Runner)          │
│         • Real-time fraud metrics                    │
│         • AI explanations                            │
│         • Campaign analysis                          │
└─────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **API Layer** | AWS API Gateway + Lambda | Serverless, auto-scaling, pay-per-request |
| **Data Ingestion** | Lambda (Python 3.11) | Simple, fast to develop, good AWS integration |
| **Storage - Real-time** | DynamoDB (on-demand) | Low latency (<10ms), serverless, no ops |
| **Storage - Analytics** | S3 (Parquet format) | Cost-effective, supports ML training |
| **ML Model** | SageMaker XGBoost | Built-in algorithm, proven for fraud detection |
| **AI Analysis** | Amazon Bedrock (Claude 3 Sonnet) | Managed LLM service, no infrastructure, pay-per-use |
| **Orchestration** | Lambda + Step Functions | Coordinate ML → AI workflow |
| **Monitoring** | CloudWatch + X-Ray | Built-in AWS monitoring, distributed tracing |
| **Dashboard** | Streamlit on App Runner | Fast Python-based UI, easy deployment |
| **IaC** | AWS SAM (CloudFormation) | Infrastructure as Code, version controlled |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
| **Version Control** | Git + GitHub | Code and infrastructure versioning |
| **Testing** | pytest + moto + Locust | Unit, integration, and load testing |

---

### CI/CD Pipeline Architecture

```
┌─────────────────────────────────────────────────────┐
│              DEVELOPER WORKFLOW                      │
└─────────────────┬───────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ↓             ↓             ↓
[Feature]     [Develop]     [Main]
  Branch        Branch       Branch
    │             │             │
    └──→ PR ──→   │             │
         │        │             │
         ↓        ↓             ↓
    ┌────────────────────────────────┐
    │      GITHUB ACTIONS            │
    │  (Automated on every commit)   │
    └────────────────────────────────┘
         │
         ↓
    ┌────────────────────┐
    │   1. CODE QUALITY  │
    │   • Linting        │
    │   • Type checking  │
    │   • Security scan  │
    └─────────┬──────────┘
              │
              ↓
    ┌────────────────────┐
    │   2. UNIT TESTS    │
    │   • Lambda tests   │
    │   • Feature tests  │
    │   • 80%+ coverage  │
    └─────────┬──────────┘
              │
              ↓
    ┌────────────────────┐
    │   3. BUILD         │
    │   • SAM build      │
    │   • Package Lambda │
    │   • Create template│
    └─────────┬──────────┘
              │
    ┌─────────┼─────────────────────┐
    ↓         ↓                     ↓
┌────────┐ ┌────────┐         ┌────────┐
│  DEV   │ │STAGING │         │  PROD  │
│  ENV   │ │  ENV   │         │  ENV   │
└────────┘ └────────┘         └────────┘
    ↑         ↑                     ↑
    │         │                     │
Auto-deploy   │              Manual Approval
on dev/      │              + Production Gate
            Auto-deploy
            on main (after tests)

    ┌─────────────────────────────────┐
    │   4. INTEGRATION TESTS          │
    │   • API endpoint tests          │
    │   • End-to-end flows            │
    │   • (Run in staging env)        │
    └─────────┬───────────────────────┘
              │
              ↓
    ┌─────────────────────────────────┐
    │   5. DEPLOY TO PRODUCTION       │
    │   • Requires approval           │
    │   • Blue-green deployment       │
    │   • Automated rollback          │
    └─────────────────────────────────┘
              │
              ↓
    ┌─────────────────────────────────┐
    │   6. POST-DEPLOYMENT            │
    │   • Smoke tests                 │
    │   • Health checks               │
    │   • Notify team                 │
    └─────────────────────────────────┘
```

---

## 5. Functional Requirements

### 5.1 Core Features

#### FR-1: Real-Time Fraud Detection API
**Priority:** P0 (Must Have)  
**Description:** RESTful API endpoint that accepts ad event data and returns fraud assessment in real-time

**API Specification:**
```json
POST /v1/detect-fraud

Request:
{
  "event_id": "uuid",
  "timestamp": "ISO-8601",
  "event_type": "click|impression|install|conversion",
  "ip_address": "string",
  "user_agent": "string",
  "device_id": "string",
  "campaign_id": "string",
  "publisher_id": "string",
  "referrer": "url",
  "click_id": "string"
}

Response (Fast Path - ML Only):
{
  "event_id": "uuid",
  "is_fraud": boolean,
  "fraud_score": 0.0-1.0,
  "confidence": 0.0-1.0,
  "detection_method": "ml_only",
  "latency_ms": integer,
  "action": "block|allow|review"
}

Response (AI-Augmented):
{
  "event_id": "uuid",
  "is_fraud": boolean,
  "fraud_score": 0.0-1.0,
  "ml_score": 0.0-1.0,
  "ai_score": 0.0-1.0,
  "confidence": 0.0-1.0,
  "detection_method": "ml_ai_ensemble",
  "fraud_signals": ["bot_detected", "suspicious_timing"],
  "reasoning": "Natural language explanation",
  "recommended_action": "block|allow|review",
  "latency_ms": integer
}
```

**Acceptance Criteria:**
- API responds within 100ms for ML-only path
- API responds within 3000ms for AI-augmented path
- API returns 400 for malformed requests with validation errors
- API returns 429 when rate limit exceeded
- API handles 1000 req/sec sustained load

#### FR-2: Two-Tier Detection Logic
**Priority:** P0 (Must Have)  
**Description:** Intelligent routing between fast ML screening and deep AI analysis

**Decision Logic:**
```
IF ml_score > 0.8:
    → Block immediately (clear fraud)
ELSE IF ml_score < 0.3:
    → Allow immediately (clear legitimate)
ELSE IF 0.3 <= ml_score <= 0.8:
    → Route to AI analysis (borderline case)
    → Ensemble ML + AI scores
    → Final decision
```

**Acceptance Criteria:**
- <20% of traffic requires AI analysis (cost optimization)
- AI analysis invoked for all scores 0.3-0.8
- High-value campaigns always get AI analysis
- Ensemble scoring weights: 40% ML, 60% AI (when AI confidence > 0.8)

#### FR-3: ML-Based Fraud Detection
**Priority:** P0 (Must Have)  
**Description:** XGBoost model trained on labeled fraud data

**Features (Minimum):**
- IP address reputation score
- Device fingerprint uniqueness
- Time since last click
- Click-to-install time (for mobile)
- User agent legitimacy score
- Geographic consistency
- Referrer validity
- Hour of day / day of week patterns

**Model Requirements:**
- Trained on minimum 100k labeled samples
- Precision > 85%, Recall > 90%
- Model updated weekly (retraining pipeline)
- Support for A/B testing of model versions

**Acceptance Criteria:**
- Model inference <50ms @ p95
- Model achieves >90% accuracy on test set
- False positive rate <5%

#### FR-4: AI-Powered Deep Analysis
**Priority:** P0 (Must Have)  
**Description:** Claude 3 Sonnet analyzes complex patterns and provides explanations

**AI Capabilities:**
- Behavioral sequence analysis (click patterns over time)
- User agent forensics (detect spoofed/bot signatures)
- Temporal anomaly detection (unnatural timing)
- Cross-event correlation (detect coordinated attacks)
- Natural language fraud explanation generation

**Prompt Engineering:**
- Structured prompt with context, ML score, and specific fraud indicators
- JSON-formatted response for consistent parsing
- Temperature: 0.1 (deterministic output)
- Max tokens: 1000

**Acceptance Criteria:**
- AI analysis completes in <3s @ p95
- AI output is valid JSON 99%+ of the time
- AI explanations are understandable to non-technical users
- AI detects fraud that ML misses in >10% of borderline cases

#### FR-5: Fraud Analytics Dashboard
**Priority:** P1 (Should Have)  
**Description:** Web-based dashboard for monitoring fraud metrics

**Dashboard Views:**
1. **Real-Time Overview**
   - Total events (last hour/day)
   - Fraud rate percentage
   - Top fraud signals
   - Geographic heatmap of fraud

2. **Campaign Analysis**
   - Fraud rate by campaign
   - Click pattern visualizations
   - AI-generated insights per campaign

3. **Event Detail View**
   - Individual event inspection
   - ML score breakdown
   - AI reasoning display
   - Full event data

**Technology:** Streamlit hosted on AWS App Runner

**Acceptance Criteria:**
- Dashboard loads in <3 seconds
- Real-time metrics update every 30 seconds
- Dashboard accessible via public URL (for demo)
- Supports viewing last 7 days of data

### 5.2 Data Management

#### FR-6: Event Storage
**Priority:** P0 (Must Have)

**Storage Strategy:**
- **DynamoDB:** Hot data (last 24 hours) for real-time queries
- **S3:** Cold storage (all historical data) in Parquet format

**DynamoDB Schema:**
```
Table: ad-events
Partition Key: event_id (String)
Sort Key: timestamp (Number)

Attributes:
- event_id (String)
- timestamp (Number - Unix epoch)
- event_type (String)
- ip_address (String)
- device_id (String)
- campaign_id (String)
- ml_score (Number)
- ai_score (Number - nullable)
- is_fraud (Boolean)
- fraud_signals (StringSet)
- reasoning (String - nullable)
- detection_method (String)

GSI-1: campaign_id + timestamp (for campaign queries)
GSI-2: device_id + timestamp (for device history)
```

**S3 Structure:**
```
s3://fraud-detection-data/
  ├── raw-events/
  │   └── date=2025-11-05/
  │       └── hour=14/
  │           └── events.parquet
  ├── training-data/
  │   ├── features.parquet
  │   └── labels.parquet
  └── models/
      └── xgboost-v1.0/
```

**Acceptance Criteria:**
- All events stored within 1 second of receipt
- S3 data partitioned by date and hour
- DynamoDB TTL set to 7 days (auto-delete old data)
- S3 lifecycle policy: archive to Glacier after 90 days

#### FR-7: Feature Engineering
**Priority:** P0 (Must Have)

**Real-Time Features (computed on-demand):**
- `ip_click_count_24h`: Clicks from IP in last 24 hours
- `device_click_count_1h`: Clicks from device in last hour
- `time_since_last_click`: Seconds since device's last click
- `ua_entropy`: User agent string entropy (complexity score)
- `geo_consistency`: IP location vs device location match

**Batch Features (pre-computed daily):**
- `ip_fraud_history`: Historical fraud rate for IP
- `campaign_fraud_rate`: Campaign's overall fraud rate
- `publisher_quality_score`: Publisher's historical quality

**Acceptance Criteria:**
- Features computed without adding >20ms to latency
- Feature values cached in DynamoDB for repeated lookups
- Feature engineering pipeline runs daily via Lambda

### 5.3 Explainability & Reporting

#### FR-8: Fraud Explanations
**Priority:** P0 (Must Have)

**Explanation Types:**
1. **ML Explanation:** Feature importance scores (SHAP values)
2. **AI Explanation:** Natural language reasoning from Claude
3. **Hybrid:** Combined ML + AI insights

**Example AI Explanation:**
```
"This click is likely fraudulent for the following reasons:
1. Bot Signature: User agent indicates headless Chrome browser
2. Unnatural Timing: Clicked exactly 1.2 seconds after page load (too consistent)
3. IP Reputation: IP address has generated 847 clicks in past hour
4. Geographic Anomaly: IP geolocates to datacenter, not residential
Recommendation: Block this traffic source immediately."
```

**Acceptance Criteria:**
- Every fraud decision includes explanation
- Explanations are <200 words
- Explanations cite specific evidence (metrics, patterns)
- Non-technical stakeholders can understand explanations

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| API Latency (ML path) | <100ms @ p95 | CloudWatch |
| API Latency (AI path) | <3000ms @ p95 | CloudWatch |
| Throughput | 1000 req/sec sustained | Load testing |
| ML Model Inference | <50ms | CloudWatch |
| AI Model Inference | <2000ms | CloudWatch |
| DynamoDB Read | <10ms | CloudWatch |
| Dashboard Load Time | <3s | Browser DevTools |

### 6.2 Reliability

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| System Uptime | 99% | CloudWatch |
| API Success Rate | 99.9% | CloudWatch |
| Data Durability | 99.999999999% (S3 standard) | AWS SLA |
| ML Endpoint Availability | 99% | SageMaker metrics |
| AI API Availability | 99.9% | Bedrock metrics |

### 6.3 Scalability

- **Vertical:** Lambda scales to 10GB memory, SageMaker to ml.g5.12xlarge
- **Horizontal:** Lambda auto-scales to 1000 concurrent executions
- **Data:** S3 unlimited, DynamoDB auto-scales with on-demand pricing
- **Cost:** Scales linearly with traffic (serverless architecture)

### 6.4 Security

| Requirement | Implementation |
|-------------|----------------|
| API Authentication | API keys via API Gateway |
| Data Encryption at Rest | KMS encryption (S3, DynamoDB) |
| Data Encryption in Transit | TLS 1.2+ |
| Secrets Management | AWS Secrets Manager |
| IAM | Least-privilege roles for all services |
| Audit Logging | CloudTrail enabled |
| DDoS Protection | AWS Shield Standard |
| Rate Limiting | API Gateway: 10k req/sec per API key |

### 6.5 Compliance

**For Prototype:** Minimal compliance requirements (GDPR basic considerations)

**Data Privacy:**
- PII handling: IP addresses hashed before storage (optional for prototype)
- Data retention: 90 days in hot storage, then archived
- Right to deletion: Manual process for prototype
- Data access logs: CloudTrail

**Future (Production):**
- GDPR compliance (EU data residency)
- CCPA compliance (California privacy rights)
- SOC 2 Type II certification
- ISO 27001 certification

---

## 7. Technical Specifications

### 7.1 ML Model Specifications

**Model Type:** XGBoost Binary Classifier

**Hyperparameters:**
```python
{
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'max_depth': 6,
    'eta': 0.1,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'num_round': 200
}
```

**Features (20 total):**

| Feature Name | Type | Description |
|--------------|------|-------------|
| ip_click_count_24h | Integer | Clicks from IP in last 24h |
| device_click_count_1h | Integer | Clicks from device in last hour |
| time_since_last_click | Float | Seconds since last click |
| hour_of_day | Integer | 0-23 |
| day_of_week | Integer | 0-6 |
| ua_is_bot | Boolean | User agent contains bot keywords |
| ua_entropy | Float | String complexity 0-1 |
| ip_is_datacenter | Boolean | IP in datacenter range |
| ip_is_vpn | Boolean | IP is known VPN |
| geo_distance_km | Float | IP geo vs device geo distance |
| referrer_is_valid | Boolean | Referrer domain is legitimate |
| click_to_view_time_ms | Integer | Time on page before click |
| campaign_fraud_rate | Float | Historical fraud rate for campaign |
| publisher_quality | Float | Publisher quality score 0-1 |
| device_fingerprint_entropy | Float | Device uniqueness score |
| is_mobile | Boolean | Mobile device or desktop |
| is_repeated_click | Boolean | Duplicate click ID |
| time_to_conversion_sec | Float | For conversion events |
| ip_country | String (encoded) | Country code |
| device_os | String (encoded) | Operating system |

**Training Data Requirements:**
- Minimum: 100,000 labeled samples
- Class balance: 70% legitimate, 30% fraud (use SMOTE if imbalanced)
- Train/Val/Test split: 70/15/15
- Update frequency: Weekly retraining

**Model Deployment:**
- SageMaker Real-Time Endpoint
- Instance: ml.t2.medium (prototype), ml.m5.large (production)
- Auto-scaling: Target 70% CPU utilization
- Model versioning: Blue-green deployment

### 7.2 AI Model Specifications

**Model:** Claude 3 Sonnet via Amazon Bedrock

**Model ID:** `anthropic.claude-3-sonnet-20240229-v1:0`

**Prompt Template:**
```python
FRAUD_ANALYSIS_PROMPT = """You are an expert ad fraud detection analyst. Analyze the following ad event and determine if it shows signs of fraudulent activity.

EVENT DATA:
===========
Event ID: {event_id}
Timestamp: {timestamp}
Event Type: {event_type}
IP Address: {ip_address}
User Agent: {user_agent}
Device ID: {device_id}
Campaign ID: {campaign_id}
Referrer: {referrer}

BEHAVIORAL CONTEXT:
===================
- This IP has generated {ip_click_count_24h} clicks in the last 24 hours
- This device has generated {device_click_count_1h} clicks in the last hour
- Time since last click from this device: {time_since_last_click} seconds
- Recent click pattern: {click_timestamps}

ML MODEL ASSESSMENT:
====================
The ML model scored this event as {ml_score:.2f} (0=legitimate, 1=fraud)
ML model flagged these features as suspicious: {ml_feature_importance}

INDUSTRY BENCHMARKS:
====================
- Normal user clicks 1-3 ads per hour
- Normal inter-click time: 30-300 seconds
- Bot signatures: Headless browsers, missing browser features
- Datacenter IPs indicate click farms

ANALYSIS REQUIREMENTS:
======================
Analyze the following aspects:
1. USER AGENT: Does it suggest automation/bot? Check for headless browser, missing features
2. CLICK PATTERNS: Are the timing patterns humanly realistic?
3. IP REPUTATION: Is the IP from a datacenter/VPN/proxy?
4. BEHAVIORAL ANOMALIES: Any unnatural patterns in the sequence?
5. CONTEXTUAL FLAGS: Does the referrer, campaign, timing make sense?

OUTPUT FORMAT (JSON ONLY):
===========================
Return ONLY valid JSON with this exact structure:
{{
    "is_fraud": true or false,
    "confidence": 0.0 to 1.0,
    "fraud_signals": ["signal1", "signal2", "signal3"],
    "reasoning": "2-3 sentence explanation citing specific evidence",
    "recommended_action": "block" or "allow" or "review",
    "primary_fraud_type": "bot_traffic" or "click_farm" or "device_farm" or "legitimate" or "unknown"
}}

IMPORTANT: Respond with ONLY the JSON object. No other text before or after."""
```

**API Parameters:**
```python
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1000,
    "temperature": 0.1,  # Low for consistency
    "top_p": 0.9,
    "messages": [{
        "role": "user",
        "content": prompt
    }]
}
```

**Error Handling:**
- Retry logic: 3 attempts with exponential backoff
- Fallback: If AI fails, use ML-only score
- Timeout: 5 seconds maximum wait
- JSON parsing: Validate response structure, fallback if invalid

### 7.3 API Specifications

**Base URL:** `https://api.fraudguard.ai/v1`

**Authentication:** API Key in header
```
X-API-Key: your_api_key_here
```

**Endpoints:**

#### POST /detect-fraud
Primary fraud detection endpoint

**Rate Limits:**
- 1000 requests/second per API key
- 100,000 requests/day per API key

**Request Headers:**
```
Content-Type: application/json
X-API-Key: string (required)
X-Request-ID: string (optional, for tracing)
```

**Error Responses:**
```json
400 Bad Request:
{
  "error": "validation_error",
  "message": "Missing required field: ip_address",
  "details": {...}
}

401 Unauthorized:
{
  "error": "authentication_failed",
  "message": "Invalid API key"
}

429 Too Many Requests:
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit: 1000 req/sec",
  "retry_after": 1
}

500 Internal Server Error:
{
  "error": "internal_error",
  "message": "System error occurred",
  "request_id": "uuid"
}
```

#### GET /events/{event_id}
Retrieve fraud analysis for specific event

**Response:**
```json
{
  "event_id": "uuid",
  "timestamp": "ISO-8601",
  "event_data": {...},
  "fraud_analysis": {...},
  "created_at": "ISO-8601"
}
```

#### GET /campaigns/{campaign_id}/analytics
Get fraud analytics for campaign

**Query Parameters:**
- `start_date` (ISO-8601)
- `end_date` (ISO-8601)

**Response:**
```json
{
  "campaign_id": "string",
  "date_range": {...},
  "total_events": integer,
  "fraud_count": integer,
  "fraud_rate": float,
  "fraud_breakdown": {
    "bot_traffic": integer,
    "click_farm": integer,
    "device_farm": integer
  },
  "top_fraud_signals": [...],
  "geographic_distribution": {...}
}
```

---

## 8. Data Flow & Processing

### 8.1 Real-Time Fraud Detection Flow

```
1. Client sends POST /detect-fraud
   ↓
2. API Gateway validates request
   ↓
3. Lambda: Ingestion Handler
   - Parse event
   - Generate event_id
   - Lookup context data (DynamoDB):
     * ip_click_count_24h
     * device_click_count_1h
     * time_since_last_click
   - Store raw event (DynamoDB + S3)
   ↓
4. Lambda: Fraud Orchestrator
   - Extract features for ML
   - Call SageMaker endpoint
   - Get ML score
   - DECISION POINT:
     IF ml_score > 0.8: → Block (fraud)
     ELSE IF ml_score < 0.3: → Allow (legit)
     ELSE: → Continue to AI analysis
   ↓
5. [CONDITIONAL] AI Analysis
   - Build prompt with event + context + ML score
   - Call Bedrock (Claude 3 Sonnet)
   - Parse JSON response
   - Extract: is_fraud, confidence, reasoning, signals
   ↓
6. Decision Combiner
   - Ensemble: final_score = (ml_score * 0.4) + (ai_score * 0.6)
   - Final verdict: fraud if final_score > 0.65
   ↓
7. Store Results
   - Update DynamoDB with fraud decision
   - Log metrics to CloudWatch
   ↓
8. Return Response to Client
   - Include: verdict, scores, reasoning, latency
```

### 8.2 Batch Analysis Flow (Daily)

```
1. EventBridge Trigger (daily at 2 AM UTC)
   ↓
2. Lambda: Batch Processor
   - Query yesterday's events from S3
   - Filter events that need re-analysis
   ↓
3. Step Functions: Orchestrate Batch
   - Process 1000 events per batch
   - Parallel execution (10 concurrent batches)
   ↓
4. Lambda: Batch AI Analyzer
   - Run AI analysis on all borderline events
   - Store enhanced results
   ↓
5. Lambda: Report Generator
   - Aggregate fraud statistics
   - Generate daily fraud report
   - Store in S3
   ↓
6. SNS: Notification
   - Email daily report to stakeholders
```

### 8.3 Model Retraining Pipeline

```
1. EventBridge Trigger (weekly, Sunday 3 AM UTC)
   ↓
2. Lambda: Data Prep
   - Extract last 7 days of labeled events from S3
   - Split train/val/test (70/15/15)
   - Store prepared datasets in S3
   ↓
3. SageMaker Training Job
   - Train XGBoost on new data
   - Hyperparameter tuning (optional)
   - Evaluate on test set
   ↓
4. Lambda: Model Evaluator
   - Compare new model vs current model
   - Metrics: AUC, precision, recall, F1
   - IF new_model_auc > current_model_auc + 0.02:
       → Deploy new model
     ELSE:
       → Keep current model
   ↓
5. SageMaker: Model Deployment
   - Blue-green deployment
   - Gradually shift traffic: 10% → 50% → 100%
   - Monitor for 24 hours
   ↓
6. SNS: Notification
   - Alert team of new model deployment
```

---

## 10. Development Timeline

### Week 1: Foundation + CI/CD Setup (5 days)
**Goal:** Basic infrastructure, data flow, and CI/CD pipeline

| Day | Tasks | Owner | Deliverables |
|-----|-------|-------|--------------|
| Mon | GitHub repo setup, branch strategy, SAM init | Dev | Repository, SAM project |
| Tue | GitHub Actions workflows, AWS credentials setup | Dev | Working CI/CD pipeline |
| Wed | Lambda functions skeleton, API endpoints, DynamoDB | Dev | Basic infrastructure |
| Thu | Generate synthetic fraud dataset, feature engineering | Dev | 100k labeled events |
| Fri | Unit tests, integration tests, deploy to dev | Dev | Working CI/CD deployment |

**Exit Criteria:**
- [ ] GitHub Actions successfully deploys to dev
- [ ] API accepts ad events and stores in DynamoDB
- [ ] 100k synthetic events generated
- [ ] Unit tests passing with >80% coverage
- [ ] Automated deployment working

### Week 2: ML Model (5 days)
**Goal:** Train and deploy XGBoost model

| Day | Tasks | Owner | Deliverables |
|-----|-------|-------|--------------|
| Mon | Prepare training data, split datasets | Dev | train.csv, val.csv, test.csv in S3 |
| Tue | Train XGBoost on SageMaker, experiment tracking | Dev | Trained model artifact |
| Wed | Evaluate model, tune hyperparameters, tests | Dev | Model metrics report, >90% accuracy |
| Thu | Deploy SageMaker endpoint to dev | Dev | Live ML endpoint |
| Fri | Integrate ML with API, end-to-end tests | Dev | ML fraud detection working |

**Exit Criteria:**
- [ ] Model achieves >90% accuracy on test set
- [ ] ML endpoint responds in <100ms
- [ ] API returns ML fraud scores
- [ ] Integration tests passing
- [ ] Load tests showing acceptable performance

### Week 3: AI Integration + Demo (5 days)
**Goal:** Add Bedrock AI layer, complete system, deliver demo

| Day | Tasks | Owner | Deliverables |
|-----|-------|-------|--------------|
| Mon | Set up Bedrock access, implement AI analyzer | Dev | AI fraud analysis function |
| Tue | Build decision combiner, ensemble logic | Dev | ML+AI integration |
| Wed | Build Streamlit dashboard, deploy to App Runner | Dev | Dashboard MVP |
| Thu | End-to-end testing, performance optimization | Dev | Production-ready system |
| Fri | Demo preparation and stakeholder demo | Dev | Successful demo delivered |

**Exit Criteria:**
- [ ] AI analysis working for borderline cases
- [ ] Dashboard shows real-time fraud metrics
- [ ] Complete demo flow functional
- [ ] All tests passing (unit, integration, load)
- [ ] Demo successfully delivered
- [ ] Stakeholder feedback collected

---

## 11. Testing Strategy

### 11.1 Automated Testing in CI/CD Pipeline

**Testing Pyramid:**
```
              ┌─────────────┐
              │   Manual    │  ← 5%  (Exploratory, UX)
              │   Testing   │
              └─────────────┘
           ┌──────────────────┐
           │  Integration &   │  ← 15% (API, E2E)
           │   Load Tests     │
           └──────────────────┘
        ┌───────────────────────┐
        │     Unit Tests        │  ← 80% (Functions, Logic)
        └───────────────────────┘
```

### 11.1.1 Unit Tests (Run on Every Commit)

**Coverage Target:** >80% for all Lambda functions

**Test Files Structure:**
```
tests/
├── unit/
│   ├── test_ingest_handler.py
│   ├── test_orchestrator.py
│   ├── test_ai_analyzer.py
│   ├── test_feature_engineering.py
│   └── test_decision_logic.py
├── integration/
│   ├── test_api_endpoints.py
│   ├── test_fraud_detection_flow.py
│   └── test_dynamodb_operations.py
├── load/
│   ├── locustfile.py
│   └── test_scenarios.py
└── smoke/
    └── test_health_checks.py
```

**Example Unit Tests:**
```python
# tests/unit/test_orchestrator.py
import pytest
from moto import mock_dynamodb, mock_sagemaker
from lambdas.orchestrator import handler

@mock_dynamodb
@mock_sagemaker
def test_ml_only_path_high_score():
    """Test ML-only decision for high fraud score"""
    event = {
        'event_data': create_test_event(),
        'ml_score': 0.95
    }
    
    response = handler.lambda_handler(event, None)
    
    assert response['is_fraud'] == True
    assert response['detection_method'] == 'ml_only'
    assert 'ai_score' not in response  # Should skip AI

@mock_dynamodb  
@mock_sagemaker
def test_ml_ai_path_borderline_score():
    """Test ML+AI decision for borderline score"""
    event = {
        'event_data': create_test_event(),
        'ml_score': 0.55
    }
    
    response = handler.lambda_handler(event, None)
    
    assert response['detection_method'] == 'ml_ai_ensemble'
    assert 'ai_score' in response
    assert 'reasoning' in response

def test_feature_extraction():
    """Test feature engineering"""
    event_data = create_test_event()
    features = extract_features(event_data)
    
    assert len(features) == 20
    assert 'ip_click_count_24h' in features
    assert features['ua_entropy'] >= 0 and features['ua_entropy'] <= 1
```

**GitHub Actions - Unit Test Job:**
```yaml
unit-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests with coverage
      run: |
        pytest tests/unit/ \
          --cov=lambdas/ \
          --cov-report=xml \
          --cov-report=term \
          --cov-fail-under=80
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
        fail_ci_if_error: true
```

### 11.1.2 Integration Tests (Run in Dev Environment)

**Test Scenarios:**
1. End-to-end fraud detection (API → ML → Response)
2. End-to-end AI-augmented detection (API → ML → AI → Response)
3. Event storage verification (DynamoDB + S3)
4. Feature enrichment with context lookups
5. Error handling (ML endpoint down, AI timeout, DynamoDB throttling)

**Example Integration Tests:**
```python
# tests/integration/test_fraud_detection_flow.py
import pytest
import requests
import boto3

DEV_API_URL = "https://dev-api.example.com/v1"

def test_complete_fraud_detection_flow():
    """Test full fraud detection from API to storage"""
    
    # 1. Send fraud event to API
    fraud_event = generate_high_fraud_event()
    response = requests.post(
        f"{DEV_API_URL}/detect-fraud",
        json=fraud_event,
        headers={'X-API-Key': os.getenv('DEV_API_KEY')}
    )
    
    # 2. Verify immediate API response
    assert response.status_code == 200
    result = response.json()
    assert result['is_fraud'] == True
    assert result['fraud_score'] > 0.7
    assert 'reasoning' in result or 'ml_score' in result
    
    event_id = result['event_id']
    
    # 3. Verify DynamoDB storage (wait for async processing)
    time.sleep(2)
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('dev-ad-events')
    item = table.get_item(Key={'event_id': event_id})
    
    assert 'Item' in item
    assert item['Item']['is_fraud'] == True
    
    # 4. Verify S3 storage
    s3 = boto3.client('s3')
    bucket = 'dev-fraud-detection-data'
    key = f"events/{event_id}.json"
    
    obj = s3.get_object(Bucket=bucket, Key=key)
    assert obj['Body'] is not None

def test_ai_analysis_triggered_for_borderline():
    """Verify AI is called for borderline ML scores"""
    
    borderline_event = generate_borderline_event()
    response = requests.post(
        f"{DEV_API_URL}/detect-fraud",
        json=borderline_event,
        headers={'X-API-Key': os.getenv('DEV_API_KEY')}
    )
    
    result = response.json()
    assert result['detection_method'] == 'ml_ai_ensemble'
    assert 'ai_score' in result
    assert 'reasoning' in result
    assert len(result['fraud_signals']) > 0
```

**GitHub Actions - Integration Test Job:**
```yaml
integration-tests:
  needs: deploy-dev
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: pip install -r requirements-dev.txt
    
    - name: Run integration tests
      env:
        DEV_API_URL: ${{ secrets.DEV_API_URL }}
        DEV_API_KEY: ${{ secrets.DEV_API_KEY }}
        AWS_REGION: us-east-1
      run: |
        pytest tests/integration/ \
          -v \
          --tb=short \
          --maxfail=3
```

### 11.1.3 Load Tests (Run in Dev Environment)

**Tool:** Locust

**Test Scenarios:**
```python
# tests/load/locustfile.py
from locust import HttpUser, task, between
import random

class FraudDetectionUser(HttpUser):
    wait_time = between(0.1, 2)
    
    def on_start(self):
        """Set API key header"""
        self.client.headers = {
            'X-API-Key': os.getenv('DEV_API_KEY'),
            'Content-Type': 'application/json'
        }
    
    @task(8)  # 80% legitimate traffic
    def detect_legitimate_traffic(self):
        """Simulate legitimate ad click"""
        event = generate_legitimate_event()
        self.client.post("/v1/detect-fraud", json=event)
    
    @task(2)  # 20% fraud traffic
    def detect_fraud_traffic(self):
        """Simulate fraudulent ad click"""
        event = generate_fraud_event()
        self.client.post("/v1/detect-fraud", json=event)
    
    @task(1)  # Occasional analytics queries
    def get_campaign_analytics(self):
        """Query campaign analytics"""
        campaign_id = random.choice(['camp_1', 'camp_2', 'camp_3'])
        self.client.get(f"/v1/campaigns/{campaign_id}/analytics")
```

**Load Test Execution:**
```bash
# Run locally or in GitHub Actions
locust -f tests/load/locustfile.py \
  --host $DEV_API_URL \
  --users 500 \
  --spawn-rate 50 \
  --run-time 5m \
  --headless
```

**Success Criteria (Prototype):**
- 500 concurrent users sustained (lower for dev environment)
- 250 req/sec sustained for 5 minutes
- P95 latency < 200ms (ML-only path)
- P95 latency < 4000ms (AI-augmented path)
- <1% error rate
- No Lambda throttling
- No DynamoDB throttling

**GitHub Actions - Load Test Job:**
```yaml
load-tests:
  needs: integration-tests
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    
    - name: Install Locust
      run: pip install locust
    
    - name: Run load tests
      env:
        DEV_API_URL: ${{ secrets.DEV_API_URL }}
        DEV_API_KEY: ${{ secrets.DEV_API_KEY }}
      run: |
        locust -f tests/load/locustfile.py \
          --host $DEV_API_URL \
          --users 500 \
          --spawn-rate 50 \
          --run-time 5m \
          --headless \
          --csv=load-test-results
    
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: load-test-results
        path: load-test-results_*.csv
    
    - name: Check performance thresholds
      run: python tests/load/check_thresholds.py
```

### 11.1.4 Smoke Tests (Run After Every Deployment)

**Purpose:** Verify basic functionality after deployment

```python
# tests/smoke/test_health_checks.py
import pytest
import requests

def test_api_health(environment_url):
    """Verify API is responding"""
    response = requests.get(f"{environment_url}/health")
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'

def test_fraud_detection_basic(environment_url, api_key):
    """Verify basic fraud detection works"""
    test_event = {
        'ip_address': '192.168.1.1',
        'user_agent': 'Mozilla/5.0',
        'device_id': 'test-device-123',
        'campaign_id': 'camp_test'
    }
    
    response = requests.post(
        f"{environment_url}/v1/detect-fraud",
        json=test_event,
        headers={'X-API-Key': api_key}
    )
    
    assert response.status_code == 200
    assert 'fraud_score' in response.json()
    assert 'is_fraud' in response.json()

def test_ml_endpoint_available(environment_url, api_key):
    """Verify ML endpoint is accessible"""
    # This will trigger ML inference
    response = requests.post(
        f"{environment_url}/v1/detect-fraud",
        json=generate_test_event(),
        headers={'X-API-Key': api_key}
    )
    
    result = response.json()
    assert 'ml_score' in result or 'fraud_score' in result
    assert response.elapsed.total_seconds() < 1.0  # Fast response
```

**GitHub Actions - Smoke Test Job:**
```yaml
smoke-tests:
  needs: deploy-production
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    
    - name: Wait for deployment to stabilize
      run: sleep 30
    
    - name: Run smoke tests
      env:
        PROD_API_URL: ${{ secrets.PROD_API_URL }}
        PROD_API_KEY: ${{ secrets.PROD_API_KEY }}
      run: |
        pytest tests/smoke/ -v --tb=short
    
    - name: Notify team if smoke tests fail
      if: failure()
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: '🚨 Production smoke tests FAILED!'
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### 11.1.5 Model Validation Tests

**Dataset:** 20k holdout test set (not seen during training)

**Automated Model Testing:**
```python
# tests/model/test_ml_model.py
import pytest
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score

def test_model_accuracy():
    """Test model achieves target accuracy"""
    test_data = pd.read_csv('tests/data/test_set.csv')
    predictions = model.predict(test_data.drop('label', axis=1))
    
    accuracy = accuracy_score(test_data['label'], predictions)
    assert accuracy > 0.90, f"Model accuracy {accuracy} below target 0.90"

def test_model_precision():
    """Test model precision > 85%"""
    test_data = pd.read_csv('tests/data/test_set.csv')
    predictions = model.predict(test_data.drop('label', axis=1))
    
    precision = precision_score(test_data['label'], predictions)
    assert precision > 0.85, f"Model precision {precision} below target 0.85"

def test_model_recall():
    """Test model recall > 90%"""
    test_data = pd.read_csv('tests/data/test_set.csv')
    predictions = model.predict(test_data.drop('label', axis=1))
    
    recall = recall_score(test_data['label'], predictions)
    assert recall > 0.90, f"Model recall {recall} below target 0.90"

def test_no_bias_by_geography():
    """Test model performance consistent across geographies"""
    test_data = pd.read_csv('tests/data/test_set.csv')
    
    for region in ['US', 'EU', 'APAC']:
        region_data = test_data[test_data['region'] == region]
        predictions = model.predict(region_data.drop('label', axis=1))
        accuracy = accuracy_score(region_data['label'], predictions)
        
        assert accuracy > 0.85, f"Model accuracy for {region}: {accuracy}"
```

### 11.1.6 Security Testing

**Automated Security Scans (Run on Every Commit):**
```yaml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    
    - name: Run Bandit (Python security)
      run: |
        pip install bandit
        bandit -r lambdas/ -f json -o bandit-report.json
    
    - name: Run Safety (dependency vulnerabilities)
      run: |
        pip install safety
        safety check --file requirements.txt --json
    
    - name: Run Semgrep (SAST)
      uses: returntocorp/semgrep-action@v1
      with:
        config: p/security-audit
    
    - name: Upload security results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: bandit-report.json
```

### 11.2 Test Coverage Requirements

| Test Type | Coverage Target | Frequency |
|-----------|----------------|-----------|
| Unit Tests | >80% line coverage | Every commit |
| Integration Tests | All critical paths | On PR, staging deploy |
| Load Tests | 1000 users, 10min | Before prod deploy |
| Smoke Tests | Core functionality | After every deploy |
| Model Tests | Full test set | Weekly retraining |
| Security Scans | All code | Every commit |

### 11.3 Continuous Monitoring (Post-Deploy)

**Real-time Testing:**
- Synthetic transactions every 5 minutes
- Canary requests to verify endpoints
- Alert on 3 consecutive failures

**A/B Testing:**
- 10% traffic to new model version
- Compare performance metrics
- Gradual rollout if successful

---

## 12. Risks & Mitigation

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Bedrock API rate limits hit** | Medium | High | Implement caching, reduce AI usage to 5%, request quota increase |
| **ML model poor accuracy** | Medium | High | Use proven XGBoost hyperparameters, ensure quality training data, iterate |
| **AI responses invalid JSON** | Medium | Medium | Robust parsing with fallback, validate response schema, retry logic |
| **Lambda cold starts cause latency** | High | Medium | Provisioned concurrency for critical functions, keep functions warm |
| **SageMaker endpoint downtime** | Low | High | Multi-AZ deployment, auto-scaling, fallback to rule-based detection |
| **DynamoDB throttling** | Low | Medium | On-demand pricing mode, implement retry with exponential backoff |
| **Cost overrun (Bedrock)** | Medium | High | Strict budget alerts, limit AI usage to 10% of traffic, cache results |
| **GitHub Actions workflow failures** | Medium | High | Retry logic, fallback to manual deployment, comprehensive error handling |
| **Deployment to wrong environment** | Low | Critical | Strict approval gates, environment naming, manual production approval |
| **Failed rollback** | Low | High | Automated CloudFormation rollback, test rollback procedures regularly |

### CI/CD Specific Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Broken main branch** | Medium | High | Require PR reviews, run all tests before merge, branch protection rules |
| **Failed deployment blocks pipeline** | Medium | Medium | Automated rollback, parallel environment deployments, manual override option |
| **Secrets leaked in code** | Low | Critical | GitHub secret scanning enabled, pre-commit hooks, rotate secrets regularly |
| **Test flakiness causes false failures** | High | Medium | Retry flaky tests 3x, fix root cause, mark known-flaky tests |
| **Load test overwhelms staging** | Low | Medium | Rate limiting on staging, separate load test environment, gradual ramp-up |
| **Production deploy without approval** | Low | Critical | GitHub environment protection rules, required approvers, audit logs |
| **Concurrent deploys cause conflicts** | Medium | Medium | Queue-based deployment, lock mechanism, clear deployment windows |

### Product Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **False positives block legit users** | High | High | Conservative fraud threshold (>0.65), human review queue for borderline |
| **Fraudsters adapt to detection** | Medium | Medium | Continuous model retraining, AI can adapt to new patterns |
| **Insufficient training data** | Medium | Medium | Use public fraud datasets + synthetic data generation |
| **Prototype not impressive enough** | Low | High | Focus on demo UX, prepare compelling fraud examples, quantify impact |
| **Multi-environment costs exceed budget** | Medium | High | Cost alerts at 80%, auto-shutdown rules, optimize AI usage |

### Timeline Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **CI/CD setup takes longer than 1 week** | Medium | Medium | Use SAM templates/examples, start simple, iterate |
| **Bedrock setup delays** | Low | Low | Have backup (SageMaker Jumpstart with Llama) |
| **ML model training takes too long** | Medium | Medium | Use SageMaker built-in XGBoost (faster), smaller dataset if needed |
| **Integration bugs delay demo** | Medium | High | Daily integration testing, build buffer time in week 4 |
| **AI prompt engineering takes longer** | Medium | Low | Start with simple prompts, iterate based on results |
| **Load testing reveals performance issues** | High | Medium | Start performance testing in week 2, optimize early |

---

## 13. Success Criteria

### Prototype Demo Success

**Must Have (MVP):**
- [ ] CI/CD pipeline fully automated (dev environment)
- [ ] Live API accepts ad events and returns fraud score in <3s
- [ ] ML model detects >90% of fraud in test dataset
- [ ] AI provides readable explanations for fraud decisions
- [ ] Dashboard displays real-time fraud metrics
- [ ] Demo flows smoothly with no crashes
- [ ] All automated tests passing (unit, integration, load)
- [ ] Zero-downtime deployments working

**Should Have:**
- [ ] AI detects fraud that ML misses (demonstrate on examples)
- [ ] False positive rate <5%
- [ ] System handles 500 req/sec in load test
- [ ] Dashboard shows geographic fraud heatmap
- [ ] Complete fraud report generated for sample campaign
- [ ] <5 minute deployment time

**Nice to Have:**
- [ ] Comparison dashboard (ML-only vs ML+AI performance)
- [ ] Real-time fraud alerting (SNS/email)
- [ ] API documentation site (Swagger/OpenAPI)
- [ ] Video demo recording

### CI/CD Pipeline Success

**Deployment Metrics:**
- [ ] Automated deployment to dev on every push to `main` branch
- [ ] Deployment time < 10 minutes
- [ ] Zero failed deployments in final week

**Testing Metrics:**
- [ ] Unit test coverage >80%
- [ ] 100% of PRs have passing tests before merge
- [ ] Integration tests run automatically after deployment
- [ ] Load tests complete without errors
- [ ] Smoke tests pass after every deployment

**Quality Metrics:**
- [ ] No security vulnerabilities in dependencies
- [ ] Code passes linting and formatting checks
- [ ] Dev environment has monitoring enabled
- [ ] CloudWatch alarms configured and tested

### Business Validation

**Prototype Phase:**
- [ ] Demo to 5+ potential customers/stakeholders
- [ ] Collect feedback: 80%+ positive reception
- [ ] Identify 2-3 pilot customer candidates
- [ ] Quantify value proposition: "$X fraud prevented per $Y spent"
- [ ] Technical documentation complete

**Post-Prototype (Future with staging/prod):**
- [ ] 3-5 pilot customers signed within 3 months
- [ ] 10:1 ROI demonstrated (save $10 fraud per $1 spent)
- [ ] <3% customer churn rate
- [ ] NPS score >50
- [ ] <30 minute mean time to recovery (MTTR)
- [ ] >99.9% uptime over 3 months

---

## 14. Open Questions & Decisions Needed

### Technical Decisions
1. **Q:** Should we use SageMaker Feature Store or build custom feature caching?
   - **Recommendation:** Custom DynamoDB caching for prototype (simpler, cheaper)
   
2. **Q:** Sync vs Async AI analysis for borderline cases?
   - **Recommendation:** Sync for prototype (simpler), async for production scale

3. **Q:** How to handle cases where AI and ML strongly disagree?
   - **Recommendation:** Trust AI when confidence >0.8, otherwise weight ensemble

4. **Q:** What fraud threshold to use? (0.6? 0.65? 0.7?)
   - **Recommendation:** Start with 0.65, tune based on false positive rate in testing

### CI/CD Decisions
1. **Q:** Should we deploy on every commit to main or require manual approval?
   - **Recommendation:** Auto-deploy on merge to `main` (faster iteration for prototype)

2. **Q:** Should we use blue-green or rolling deployments?
   - **Recommendation:** SAM default (CloudFormation update), add blue-green post-prototype

3. **Q:** What should trigger a rollback?
   - **Recommendation:** >5% error rate for 5min, P95 latency >5s, or manual trigger

4. **Q:** How long should we keep old Lambda versions?
   - **Recommendation:** 3 most recent versions for fast rollback

5. **Q:** Should we run load tests on every deploy?
   - **Recommendation:** Run on-demand during testing phase, not on every commit

6. **Q:** When should we add staging and production environments?
   - **Recommendation:** After successful demo and pilot customer sign-up

### Product Decisions
1. **Q:** Should we label fraud by type (bot, click farm, etc.)?
   - **Recommendation:** Yes, AI should classify fraud type for better insights

2. **Q:** Do we need real-time alerting for high fraud rates?
   - **Recommendation:** Yes, alert if fraud rate >30% for 15 minutes

3. **Q:** Should dashboard be public (for demo) or authenticated?
   - **Recommendation:** Public with obscured data for demo, add auth post-demo

4. **Q:** Do we need audit logs for all fraud decisions?
   - **Recommendation:** Yes, CloudTrail + DynamoDB Streams for full audit trail

### Business Decisions
1. **Q:** What is acceptable cost per 10k events analyzed?
   - **Recommendation:** <$2 for MVP to demonstrate viability

2. **Q:** Who are the initial target customers for pilot?
   - **Recommendation:** Mid-size ad networks and performance marketing agencies

3. **Q:** What is the minimum contract size for pilot customers?
   - **Recommendation:** $5k-10k for 3-month pilot

4. **Q:** Should we open-source any components?
   - **Recommendation:** Consider open-sourcing synthetic data generator for community goodwill

---

## 15. Future Enhancements (Post-Prototype)

### Phase 2 Features (Production)
1. **Real-time Alerting:** SNS/Email when fraud rate spikes
2. **Custom Rules Engine:** Allow customers to define custom fraud rules
3. **Webhook Integration:** Push fraud decisions to customer systems
4. **Advanced Analytics:** Fraud trends, predictive forecasting
5. **Multi-tenancy:** Support multiple customers on same platform
6. **White-label Dashboard:** Branded for each customer

### Phase 3 Features (Scale)
1. **Graph Database:** Neo4j for detecting fraud networks/rings
2. **Behavioral Biometrics:** Mouse movements, typing patterns
3. **Device Fingerprinting:** More sophisticated device tracking
4. **Blockchain Verification:** Immutable fraud audit trail
5. **Automated Blocking:** Auto-block IPs/devices with high fraud scores
6. **ML Model Marketplace:** Multiple models for different fraud types

### AI Enhancements
1. **Fine-tuned Model:** Train Claude specifically on ad fraud data
2. **Multi-modal Analysis:** Analyze ad creative images for fraud patterns
3. **Conversational Interface:** Chat with AI about fraud patterns
4. **Automated Prompt Optimization:** A/B test prompts for best results
5. **Explainable AI Dashboard:** Visual SHAP values + AI reasoning

### CI/CD & DevOps Enhancements
1. **Multi-Region Deployment:** Deploy to multiple AWS regions for global coverage
2. **Canary Deployments:** Gradual traffic shift (5% → 25% → 50% → 100%)
3. **Feature Flags:** Toggle features without deployment (LaunchDarkly)
4. **Chaos Engineering:** Automated resilience testing (AWS Fault Injection Simulator)
5. **Performance Regression Testing:** Automated performance baselines
6. **Cost Anomaly Detection:** ML-based cost spike alerting
7. **Automated Security Patching:** Auto-update dependencies with vulnerabilities
8. **Infrastructure Drift Detection:** Alert on manual console changes
9. **Compliance as Code:** Automated compliance checks (AWS Config Rules)
10. **Multi-Cloud Support:** Terraform for AWS + GCP deployment

### Monitoring & Observability
1. **Distributed Tracing:** AWS X-Ray + Jaeger for full request tracing
2. **Real User Monitoring (RUM):** Track actual user experience
3. **Synthetic Monitoring:** Datadog/New Relic synthetic transactions
4. **Log Aggregation:** ELK stack or CloudWatch Logs Insights
5. **Anomaly Detection:** ML-based anomaly alerts (CloudWatch Anomaly Detection)
6. **SLO/SLI Tracking:** Service-level objectives and indicators
7. **On-call Rotation:** PagerDuty integration for incident management

---

## 16. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Ad Fraud** | Fraudulent activity designed to generate illegitimate ad revenue |
| **Bot Traffic** | Non-human traffic generated by automated scripts |
| **Click Farm** | Operation using real devices/humans to generate fake clicks |
| **Device Farm** | Collection of devices used to simulate legitimate traffic |
| **Click Injection** | Fraud technique where clicks are injected just before app install |
| **Domain Spoofing** | Faking the domain where an ad is displayed |
| **IVT** | Invalid Traffic - non-human or fraudulent traffic |
| **CTIT** | Click-Through Invalid Traffic |
| **Attribution Fraud** | Falsely claiming credit for conversions |
| **SDK Spoofing** | Faking legitimate app SDK signals |

### Appendix B: Sample Datasets

**Public Fraud Datasets for Training:**
1. **Kaggle - Click Fraud Detection**
   - 200k+ labeled mobile ad clicks
   - URL: https://www.kaggle.com/c/talkingdata-adtracking-fraud-detection

2. **IEEE-CIS Fraud Detection**
   - Transaction-based fraud (adaptable)
   - URL: https://www.kaggle.com/c/ieee-fraud-detection

**Synthetic Data Generation:**
```python
# fraud_data_generator.py
from faker import Faker
import random
import pandas as pd

fake = Faker()

def generate_legitimate_click():
    return {
        'event_id': fake.uuid4(),
        'timestamp': fake.unix_time(),
        'ip_address': fake.ipv4_public(),
        'user_agent': fake.user_agent(),
        'device_id': fake.uuid4(),
        'campaign_id': f'camp_{random.randint(1, 100)}',
        'is_fraud': False
    }

def generate_fraud_click():
    fraud_patterns = ['bot', 'click_farm', 'device_farm']
    pattern = random.choice(fraud_patterns)
    
    event = generate_legitimate_click()
    event['is_fraud'] = True
    
    if pattern == 'bot':
        event['user_agent'] = 'Mozilla/5.0 (compatible; Bot/1.0)'
        event['ip_address'] = '192.168.1.1'  # Datacenter IP
    
    elif pattern == 'click_farm':
        event['ip_address'] = f'45.{random.randint(1,255)}.0.1'  # Same IP range
        event['device_id'] = f'device_{random.randint(1, 10)}'  # Limited devices
    
    return event

# Generate 100k samples (70% legit, 30% fraud)
data = []
for i in range(100000):
    if random.random() < 0.7:
        data.append(generate_legitimate_click())
    else:
        data.append(generate_fraud_click())

df = pd.DataFrame(data)
df.to_csv('training_data.csv', index=False)
```

### Appendix C: References

**Research Papers:**
1. "Ad Fraud Detection Using Machine Learning" - IEEE 2023
2. "Large Language Models for Fraud Detection" - NeurIPS 2024
3. "Real-Time Fraud Detection in Digital Advertising" - KDD 2023

**Industry Reports:**
1. White Ops (HUMAN) Bot Baseline Report 2024
2. Association of National Advertisers (ANA) Fraud Study
3. Integral Ad Science Media Quality Report

**AWS Documentation:**
- [Amazon Bedrock Developer Guide](https://docs.aws.amazon.com/bedrock/)
- [SageMaker XGBoost Algorithm](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-05 | Lumina | Initial PRD draft |
| 2.0 | 2025-11-06 | Lumina | Updated for full CI/CD deployment approach |
| 2.1 | 2025-11-06 | Lumina | Simplified to dev environment only for prototype |

**Approvals Required:**
- [ ] Technical Lead Review
- [ ] Product Manager Approval  
- [ ] Security Review (basic for prototype)
- [ ] DevOps Lead Review (CI/CD pipeline approval)

**Next Steps:**
1. Review PRD with team
2. Get approvals
3. Set up GitHub repository and CI/CD pipeline (Week 1, Days 1-2)
4. Set up AWS dev environment
5. Begin development
6. Daily standups to track progress

**Timeline:** 3 weeks total
- Week 1: Foundation + CI/CD setup
- Week 2: ML Model
- Week 3: AI Integration + Demo

---

**Questions or Feedback?**
Contact: lumina@fraudguard.ai