# Google Ads Integration - Implementation Guide

## Overview

This document provides comprehensive implementation requirements and step-by-step guidance for integrating Google Ads Parallel Tracking (Phase 1) with the FraudGuard system. Google requires <1 second response time or it stops sending tracking requests.

**Integration Purpose:**
- Enable Google Ads Parallel Tracking for async fraud detection
- Capture all data required for Google refund claims
- Build foundation for Phase 2 (Custom Domain Tracking with real-time blocking)

**Phase 1 vs Phase 2:**
- **Phase 1 (MVP):** Google Parallel Tracking - Easy setup, async fraud detection, no DNS required
- **Phase 2 (Premium):** Custom Domain Tracking - Real-time blocking with customer's branded subdomain

**Critical Requirements:**
- Response time < 1 second (Google timeout threshold)
- Target: < 500ms p95 response time
- 204 No Content status code
- Async processing must not block response

---

## Configuration Decisions

### 1. API Gateway Type: REST API

**Choice:** REST API (not HTTP API)

**Reasoning:**
- Need rate limiting and throttling controls for production fraud detection
- API keys support for future customer authentication
- Usage plans capability for potential tiered pricing
- More control over CORS and security policies
- Cost difference negligible at expected scale

**Configuration:**
- API Name: `PlatformAPI`
- Stage: `prod`
- Throttling: 10,000 requests/second burst, 5,000 sustained
- Enable CORS for future dashboard integration

---

### 2. CloudWatch Alarms: Create SNS Topic

**Choice:** Create new SNS topic

**SNS Topic Configuration:**
- Topic Name: `PlatformOpsAlerts`
- Email Subscription: [YOUR_EMAIL_HERE]
- Purpose: Infrastructure health alerts for entire platform (not just FraudGuard)

**Required Alarms:**
1. **Google Ads Endpoint Performance**
   - Metric: `/pt` endpoint response time
   - Threshold: > 900ms (approaching Google's 1 second timeout)
   - Action: Send SNS notification
   - Priority: CRITICAL (Google stops sending requests if you timeout)

2. **Error Rate**
   - Metric: API Gateway 5xx errors or Lambda errors
   - Threshold: > 1% error rate
   - Action: Send SNS notification
   - Priority: HIGH

3. **Lambda Throttling**
   - Metric: Throttled Lambda invocations
   - Threshold: > 0 (any throttling is bad)
   - Action: Send SNS notification
   - Priority: HIGH

4. **DynamoDB Throttling**
   - Metric: Throttled DynamoDB operations
   - Threshold: > 0
   - Action: Send SNS notification
   - Priority: MEDIUM

5. **No Traffic Alarm**
   - Metric: Zero requests to `/pt` for 5 minutes
   - Action: Send SNS notification
   - Priority: CRITICAL (system down or Google stopped sending)

6. **Cost Spike Alarm**
   - Metric: Lambda costs spike
   - Action: Send SNS notification
   - Priority: HIGH (cost protection)

---

### 3. API Gateway Configuration: Explicit Resources

**Choice:** Explicit API Gateway resources (not SAM Events syntax)

**Reasoning:**
- Need precise control over throttling per endpoint
- Custom CORS configuration
- Easier to add custom domain later (Phase 2)
- Better visibility into API Gateway configuration
- Supports future expansion (webhooks, customer API endpoints)

**Required Endpoints:**
```
POST /v1/detect-fraud → IngestionHandler (existing)
GET  /pt               → GoogleAdsTrackingHandler (new)
```

---

## Architecture Changes

### 1. API Gateway Configuration
**File:** `template.yaml`

**Add:**
- REST API Gateway resource (explicit resources, not SAM Events syntax)
- Two routes:
  - `POST /v1/detect-fraud` → Existing IngestionHandler
  - `GET /pt` → New GoogleAdsTrackingHandler

**API Gateway Resources:**
- `AWS::ApiGateway::RestApi` (PlatformAPI)
- `AWS::ApiGateway::Resource` (for each path)
- `AWS::ApiGateway::Method` (POST/GET)
- `AWS::ApiGateway::Deployment` (prod stage)
- `AWS::ApiGateway::Stage` (prod)

**Outputs:**
- `ApiUrl`: API Gateway endpoint URL
- `ApiId`: API Gateway ID

---

### 2. New Lambda Function
**File:** `src/google_ads_tracking/app.py` (NEW)

**Requirements:**
- Handle GET requests with query parameters
- Respond with 204 No Content in < 1 second (critical)
- Process fraud detection asynchronously after response
- Map Google Ads parameters to event structure
- Trigger async processing via SQS or direct Lambda invocation

**Lambda Configuration:**
- Memory: 1024 MB (provides more CPU for faster processing)
- Timeout: 5 seconds (1 second for response, 4 seconds for async processing)
- Reserved Concurrency: Consider setting based on expected traffic
- Environment Variables:
  - `FRAUD_THRESHOLD`: Fraud score threshold (configurable, not hardcoded)
  - `EVENTS_TABLE_NAME`: DynamoDB table name
  - `ORCHESTRATOR_FUNCTION`: Orchestrator Lambda ARN

**Key Implementation:**
- Extract and validate query params immediately (fail fast on invalid input)
- Return 204 response immediately (before any processing)
- Use Python threading/async for background processing (after response)
- Map Google params: cid→campaign_id, gclid→click_id, kw→keyword, aid→ad_group_id, target→target_id
- Capture all fields required for Google refund compatibility

**New File:** `src/google_ads_tracking/requirements.txt`
- boto3 (for Lambda invocation)
- Standard library only (minimize cold start)

---

### 3. Event Structure Mapping

**Google Ads → FraudGuard Event Mapping:**

```python
{
    # Google Ads Parameters (from query string)
    'cid': 'campaign_id',
    'gclid': 'click_id',  # Google Click ID (CRITICAL for refunds)
    'kw': 'keyword',
    'aid': 'ad_group_id',
    'target': 'target_id',
    
    # Optional Google Ads Parameters
    'mt': 'match_type',  # exact, phrase, broad
    'device': 'device',   # mobile, desktop, tablet
    'creative': 'creative_id',
    
    # Derived Fields
    'event_type': 'click',
    'source': 'google_ads',
    'timestamp': int(datetime.now().timestamp()),
    
    # Not available in parallel tracking (Phase 1)
    'ip_address': None,  # Not available in parallel tracking
    'device_id': None,   # Not available in parallel tracking
    'user_agent': None,  # Not available in parallel tracking
    'referrer': None,    # Not available in parallel tracking
}
```

**Data Capture Requirements (Google Refund Compatibility):**

The GoogleAdsTrackingHandler MUST capture all fields required for Google's Click Quality Form refund process:

**Required Fields for Google Refunds:**
- Date/time of clicks → `timestamp`
- GCLID values → `gclid`
- IP addresses → `ip_address` (not available in Phase 1, but structure for Phase 2)
- Affected campaigns → `campaign_id`
- Affected ad groups → `ad_group_id`
- Keywords → `keyword`
- Placement/Target IDs → `target_id`
- Web logs/tracking data → all fields combined

---

### 4. DynamoDB Schema Updates
**File:** `template.yaml` (EventsTable)

**Add Global Secondary Indexes:**
1. `gclid-timestamp-index`
   - Partition Key: gclid
   - Sort Key: timestamp
   - Purpose: Look up click history by Google Click ID (for refund exports)

2. `keyword-timestamp-index`
   - Partition Key: keyword
   - Sort Key: timestamp
   - Purpose: Calculate historical fraud rates by keyword

3. `target-timestamp-index`
   - Partition Key: target_id
   - Sort Key: timestamp
   - Purpose: Calculate fraud rates by placement/audience

4. `campaign-timestamp-index` (if not already exists)
   - Partition Key: campaign_id
   - Sort Key: timestamp
   - Purpose: Query all clicks for a campaign (for refund exports)

**Add Attribute Definitions:**
- `gclid` (S) - String type
- `keyword` (S) - String type
- `target_id` (S) - String type

**EventsTable Schema (ALL required for Google refund claims):**

```python
{
  # Primary Key
  'event_id': 'uuid',
  'timestamp': 1699564800,
  
  # Source Identification
  'source': 'google_ads',
  'event_type': 'click',
  
  # Google Ads identifiers (REQUIRED for refunds)
  'gclid': 'abc123',              # CRITICAL for refunds
  'campaign_id': 'campaign_456',
  'ad_group_id': 'adgroup_789',   # REQUIRED for refunds
  'keyword': 'buy shoes online',   # REQUIRED for refunds
  'target_id': 'placement_xyz',    # REQUIRED for refunds
  'match_type': 'exact',
  'device': 'mobile',
  'creative_id': 'creative_123',
  
  # Network/browser data (Phase 2 - not available in Phase 1)
  'ip_address': None,             # REQUIRED for refunds (Phase 2)
  'user_agent': None,
  'referrer': None,
  'accept_language': None,
  
  # Fraud detection
  'fraud_score': 0.85,
  'is_fraud': True,
  'fraud_indicators': ['repeat_ip', 'suspicious_timing'],
  'ml_score': 0.82,
  'ai_score': 0.88,
  'detection_method': 'ml_ai_ensemble',
  
  # Optional geo data
  'geo_country': 'US',
  'geo_region': 'CA',
  'geo_city': 'San Francisco'
}
```

**Provisioned vs On-Demand:**
- Start with On-Demand (pay per request)
- Switch to Provisioned if traffic becomes predictable
- Enables DynamoDB Auto Scaling

---

### 5. Feature Extraction Updates
**File:** `src/orchestrator/feature_extractor.py`

**Add Google-Specific Features:**
- `keyword_fraud_rate`: Historical fraud rate for this keyword (query DynamoDB)
- `target_fraud_rate`: Historical fraud rate for this placement/target (query DynamoDB)
- `gclid_pattern_score`: Pattern analysis of GCLID (entropy, frequency)
- `campaign_fraud_rate`: Historical fraud rate for campaign (already exists)

**Add Helper Functions:**
- `get_keyword_fraud_rate(table_name, keyword, days=30)`: Query DynamoDB for keyword fraud rate
- `get_target_fraud_rate(table_name, target_id, days=30)`: Query DynamoDB for target fraud rate
- `analyze_gclid_pattern(gclid)`: Analyze GCLID for bot-like patterns

**Update `extract_features()` Function:**
- Handle events with limited signals (no IP/device/user agent for Google Ads events)
- Use pattern-based detection when browser signals unavailable
- Skip IP/device-based features when unavailable (source = 'google_ads')

---

### 6. Update Orchestrator for Google Ads Events
**File:** `src/orchestrator/app.py`

**Detect Google Ads Events:**
- Identify events with `source = 'google_ads'`
- Skip IP/device-based features when unavailable
- Use pattern-based detection (keyword/target fraud rates)
- Adjust fraud detection logic for limited-signal events

---

### 7. Update Storage Utilities
**File:** `src/storage/dynamodb_utils.py`

**Add Functions:**
- `query_events_by_gclid(table_name, gclid, start_timestamp, end_timestamp)`: Query by GCLID
- `query_events_by_keyword(table_name, keyword, start_timestamp, end_timestamp)`: Query by keyword
- `query_events_by_target(table_name, target_id, start_timestamp, end_timestamp)`: Query by target
- `get_keyword_fraud_rate(table_name, keyword, days=30)`: Calculate historical fraud rate for keyword
- `get_target_fraud_rate(table_name, target_id, days=30)`: Calculate historical fraud rate for target

---

## Phase 1 Performance Optimizations

### Lambda Configuration

**GoogleAdsTrackingHandler (NEW):**
- Memory: 1024 MB (provides more CPU for faster processing)
- Timeout: 5 seconds (1 second for response, 4 seconds for async processing)
- Reserved Concurrency: Consider setting based on expected traffic

**Orchestrator Lambda:**
- Memory: 1024 MB (up from default)
- Rationale: Speeds up async fraud detection from 1-2s → 0.5-1s
- Cost: ~$0.50 extra per million invocations (negligible)

**FeatureExtractor Lambda:**
- Memory: 1024 MB
- Rationale: Faster historical fraud rate calculations

### Caching Strategy

**In-Memory Caching (Implement in Lambda code):**

Cache these lookups in Lambda memory:
- Keyword fraud rates (cache for 5 minutes)
- Placement/target fraud rates (cache for 5 minutes)
- Campaign fraud rates (cache for 5 minutes)

**Benefits:**
- Reduces DynamoDB reads by ~80%
- Free (just code changes)
- Lambda containers persist across invocations

**Implementation:**
```python
# Simple in-memory cache with TTL
cache = {}
CACHE_TTL = 300  # 5 minutes

def get_cached_fraud_rate(key, fetch_func):
    now = time.time()
    if key in cache:
        value, timestamp = cache[key]
        if now - timestamp < CACHE_TTL:
            return value
    value = fetch_func()
    cache[key] = (value, now)
    return value
```

---

## Implementation Requirements

### 1. Configuration Management

**Requirement:** All thresholds and business logic MUST be configurable, not hardcoded.

**Implementation:**
- Fraud score threshold → Environment variable or DynamoDB config table
- Rate limits → API Gateway configuration (not hardcoded in Lambda)
- Feature flags → For toggling features without redeployment
- Customer-specific settings → Stored in config table, not code

**Why:** Different customers need different thresholds. B2B vs B2C vs ecommerce have different fraud patterns. Hardcoding = technical debt from day 1.

**Example:**
```python
# ❌ BAD - Hardcoded
if (fraudScore > 0.7) { markAsFraud(); }

# ✅ GOOD - Configurable
threshold = os.environ.get('FRAUD_THRESHOLD', '0.65')
if fraud_score > float(threshold):
    mark_as_fraud()
```

---

### 2. Input Validation & Security

**Requirement:** Validate and sanitize ALL inputs before processing.

**Implementation:**
- API Gateway request validation (reject malformed requests before hitting Lambda)
- Lambda parameter validation (type checking, range validation)
- SQL injection prevention (use parameterized queries - DynamoDB handles this)
- XSS prevention (sanitize any user-provided strings)
- Rate limiting per customer/IP to prevent abuse

**Why:** Malicious tracking URLs could exploit vulnerabilities, crash Lambdas, or run up your AWS bill. One bad actor can cause thousands in Lambda costs if not rate-limited.

**Input Validation Schema:**

```python
# Validate all Google Ads parameters
VALIDATION_SCHEMA = {
    'gclid': {
        'type': str,
        'max_length': 100,
        'pattern': r'^[a-zA-Z0-9_-]+$',
        'required': False
    },
    'cid': {
        'type': str,
        'max_length': 50,
        'pattern': r'^[a-zA-Z0-9_-]+$',
        'required': True
    },
    'kw': {
        'type': str,
        'max_length': 200,
        'required': False,
        'sanitize': True  # Sanitize for XSS
    },
    'aid': {
        'type': str,
        'max_length': 50,
        'pattern': r'^[a-zA-Z0-9_-]+$',
        'required': False
    },
    'target': {
        'type': str,
        'max_length': 200,
        'required': False
    }
}

def validate_google_ads_params(query_params):
    """Validate and sanitize Google Ads query parameters"""
    errors = []
    validated = {}
    
    for param, schema in VALIDATION_SCHEMA.items():
        value = query_params.get(param)
        
        if schema.get('required') and not value:
            errors.append(f"Missing required parameter: {param}")
            continue
        
        if value:
            # Type checking
            if not isinstance(value, schema['type']):
                errors.append(f"Invalid type for {param}: expected {schema['type']}")
                continue
            
            # Length checking
            if 'max_length' in schema and len(value) > schema['max_length']:
                errors.append(f"Parameter {param} exceeds max length: {schema['max_length']}")
                continue
            
            # Pattern matching
            if 'pattern' in schema:
                import re
                if not re.match(schema['pattern'], value):
                    errors.append(f"Parameter {param} does not match required pattern")
                    continue
            
            # Sanitize for XSS
            if schema.get('sanitize'):
                value = sanitize_string(value)
            
            validated[param] = value
    
    if errors:
        return None, errors
    
    return validated, None
```

**Error Handling:**
- Generic error messages (no internal details leaked)
- Return 400 Bad Request for validation errors
- Return 204 No Content for successful requests (even if async processing fails)

---

### 3. Rate Limiting & Cost Protection

**Requirement:** Implement rate limiting at multiple layers to prevent runaway costs.

**Implementation:**
- API Gateway throttling: 10,000 burst, 5,000 sustained (per account/API key)
- Lambda reserved concurrency: Limit max concurrent executions
- DynamoDB provisioned throughput or on-demand with alarms
- Per-customer rate limits (prevent one customer from crushing system)

**Why:** A single malicious actor hitting your `/pt` endpoint can generate millions of Lambda invocations = massive AWS bill. Without rate limiting, you're exposed.

**API Gateway Throttling Configuration:**

```yaml
# API Gateway throttling per customer
UsagePlan:
  Throttle:
    BurstLimit: 1000
    RateLimit: 500
  Quota:
    Limit: 1000000  # 1M requests per month
    Period: MONTH
```

**Lambda Reserved Concurrency:**
- Set reserved concurrency on GoogleAdsTrackingHandler to prevent cost spikes
- Example: 100 concurrent executions max
- Prevents runaway costs from malicious requests

---

### 4. Monitoring & Alerting (Non-negotiable)

**Requirement:** If Google stops sending tracking requests, you MUST know immediately.

**Implementation:**
- CloudWatch alarm: Zero requests to `/pt` for 5 minutes → Alert
- CloudWatch alarm: Response time > 900ms → Alert (Google will timeout at 1s)
- CloudWatch alarm: Error rate > 1% → Alert
- CloudWatch alarm: Lambda costs spike → Alert (cost protection)
- CloudWatch Dashboard: Real-time visibility into system health

**Why:** Google stops sending parallel tracking requests if you timeout repeatedly. Without monitoring, you won't know your fraud detection is broken until customers complain.

**Required Alarms:**
1. No traffic alarm (system down or Google stopped sending)
2. Slow response alarm (approaching Google's 1s timeout)
3. Error rate alarm (bugs in production)
4. Cost spike alarm (runaway Lambda costs)
5. Lambda throttling alarm (any throttling is bad)
6. DynamoDB throttling alarm (capacity issues)

**CloudWatch Dashboard:**

**Metrics to Display:**
1. `/pt` endpoint latency (p50, p95, p99)
2. API Gateway request count
3. Lambda invocation count and duration
4. Lambda error count
5. DynamoDB throttling events
6. Fraud detection rate (% flagged as fraud)

**Purpose:**
- Real-time visibility into system health
- Identify fraud patterns (which keywords/placements are high-fraud)
- Debug performance issues

---

### 5. Documentation (Code & Customer)

**Requirement:** Document architecture, decisions, and customer setup from day 1.

**Implementation:**
- Architecture diagram in repository
- README with setup instructions
- Inline code comments for complex logic
- Customer documentation with screenshots
- Runbook for common issues (slow responses, missing clicks, etc.)
- Decision log (why we chose REST API over HTTP API, etc.)

**Why:** In 6 months when something breaks at 2am, you need to remember how it works. When customers struggle with setup, they need clear documentation. Future team members need context for architecture decisions.

**Required Documentation:**
- `/docs/ARCHITECTURE.md` - System design and data flow
- `/docs/RUNBOOK.md` - How to debug common issues
- `/docs/CUSTOMER_SETUP.md` - How to configure Google Ads tracking
- Code comments - Complex fraud detection logic
- Inline comments - Non-obvious business rules

---

## Implementation Steps

### Step 1: Add API Gateway to template.yaml
- Create REST API Gateway resource (explicit resources, not SAM Events syntax)
- Configure CORS
- Add routes for both endpoints:
  - `POST /v1/detect-fraud` → IngestionHandler
  - `GET /pt` → GoogleAdsTrackingHandler
- Set up API Gateway throttling (10,000 burst, 5,000 sustained)
- Add API Gateway outputs (ApiUrl, ApiId)

### Step 2: Create GoogleAdsTrackingHandler Lambda
- Create `src/google_ads_tracking/` directory
- Implement handler that:
  1. Extracts and validates query parameters (fail fast on invalid input)
  2. Responds immediately with 204 No Content (< 1 second)
  3. Triggers async processing via direct Lambda invocation
- Map Google Ads parameters to event structure
- Capture all fields required for Google refund compatibility

### Step 3: Update DynamoDB Schema
- Add new GSIs for Google Ads lookups:
  - `gclid-timestamp-index`
  - `keyword-timestamp-index`
  - `target-timestamp-index`
- Add attribute definitions (gclid, keyword, target_id)
- Update table definition in template.yaml

### Step 4: Enhance Feature Extractor
- Add functions to query historical fraud rates:
  - `get_keyword_fraud_rate()`
  - `get_target_fraud_rate()`
  - `analyze_gclid_pattern()`
- Implement Google-specific feature extraction
- Update feature vector to include new features
- Add in-memory caching for fraud rate lookups

### Step 5: Update Orchestrator
- Handle events with limited signals (no IP, device, user agent)
- Adjust fraud detection logic for Google Ads events
- Use pattern-based detection when browser signals unavailable
- Detect Google Ads events (source = 'google_ads')

### Step 6: Update Storage Utilities
- Add DynamoDB query functions for Google Ads data:
  - `query_events_by_gclid()`
  - `query_events_by_keyword()`
  - `query_events_by_target()`
  - `get_keyword_fraud_rate()`
  - `get_target_fraud_rate()`

### Step 7: Add CloudWatch Alarms
- Create SNS topic: `PlatformOpsAlerts`
- Create CloudWatch alarms:
  - Google Ads endpoint performance (> 900ms)
  - Error rate (> 1%)
  - Lambda throttling (> 0)
  - DynamoDB throttling (> 0)
  - No traffic (zero requests for 5 minutes)
  - Cost spike (Lambda costs)
- Configure SNS email subscription

### Step 8: Create CloudWatch Dashboard
- Create dashboard for Google Ads tracking metrics
- Display: response time, request count, error rate, fraud detection rate

---

## Performance Requirements

### Critical for Google Parallel Tracking:
- **Response Time:** < 1 second (target: < 500ms)
- **Status Code:** 204 No Content
- **Timeout:** Google will timeout after 1 second
- **Async Processing:** Must not block response

### Performance Targets (Phase 1)

**GoogleAdsTrackingHandler Response:**
- Target: <500ms for 204 response
- Maximum: <1000ms (Google's hard timeout)
- Expected: 50-150ms with optimizations

**Background Fraud Detection:**
- Target: <1 second end-to-end (after 204 response)
- Expected: 300-800ms with 1024 MB Lambda and caching
- Not user-facing, so less critical

**Success Criteria:**
- ✅ Zero timeouts from Google Ads
- ✅ <1% error rate
- ✅ Fraud detection completes within 1 second of receiving click
- ✅ System handles 1000+ requests/second without throttling

---

## Security Requirements

### API Gateway:
- Rate limiting (10,000 burst, 5,000 sustained)
- CORS configuration (restrictive)
- HTTPS enforcement (all endpoints require HTTPS)
- Optional API key authentication (for future customer authentication)

### Lambda:
- Input validation (strict schema validation)
- Parameter sanitization (XSS prevention)
- Error handling (generic error messages, no internal details)
- Reserved concurrency (prevent cost spikes)

### Security Best Practices:
- All endpoints require HTTPS
- Input validation on all parameters
- Rate limiting via API Gateway
- Lambda reserved concurrency limits
- Generic error messages (no information leakage)
- Sanitize all user-provided strings

---

## Testing Strategy

### Unit Tests:
- Test parameter mapping
- Test immediate response (204)
- Test async processing trigger
- Test input validation
- Test error handling

### Integration Tests:
- Test full flow: Google request → 204 response → fraud detection
- Test with real Google Ads tracking URLs
- Verify DynamoDB storage
- Test error scenarios

### Performance Tests:
- Measure response time (must be < 1s)
- Load test with high volume of requests (1000+ req/sec)
- Test timeout scenarios
- Verify CloudWatch alarms trigger correctly

---

## What NOT to Implement (Phase 1)

These optimizations provide minimal value for Phase 1's async processing model:

❌ **EdgeOptimized API Gateway**
- Reason: Google makes requests from their servers (likely us-east-1), not end users
- Save for: Phase 2 when actual users worldwide click ads

❌ **DynamoDB DAX (caching layer)**
- Reason: Expensive (~$86/month) with no benefit for async processing
- Cost: $0.12/hour
- Save for: Phase 2 if DynamoDB becomes a bottleneck for <200ms response

❌ **Lambda@Edge**
- Reason: Not applicable for Phase 1 architecture
- Save for: Phase 2 if needed for global latency reduction

---

## Google Ads Refund Integration

### Background
Google provides a Click Quality Form where advertisers can request refunds for invalid/fraudulent clicks. Approval rate is ~10% with 30-50% of requested amount typically granted. Process takes 2-6+ weeks.

### Data Requirements
FraudGuard must capture and store all fields Google requires:

**Required Fields:**
- ✅ Date/time of clicks → `timestamp`
- ✅ GCLID (Google Click ID) → `gclid`
- ✅ IP addresses → `ip_address` (Phase 2)
- ✅ Campaign IDs → `campaign_id`
- ✅ Ad Group IDs → `ad_group_id`
- ✅ Keywords → `keyword`
- ✅ Placement/Target IDs → `target_id`
- ✅ Web logs/tracking data → all fields combined

**Our Advantage:**
Unlike competitors who only show "fraud detected," we capture ALL data needed for refund claims, making it trivial for customers to request refunds from Google.

### Export Feature (P2)

**Dashboard Feature: "Export for Google Refund"**

Allow customers to:
1. Select date range
2. Select campaign(s)
3. Filter by fraud score threshold
4. Generate CSV with exact format Google expects

**CSV Columns:**
```
Date/Time | GCLID | IP Address | Campaign | Ad Group | Keyword | Placement | Fraud Score | User Agent | Referer
```

**Implementation Notes:**
- Query DynamoDB by campaign_id and timestamp range
- Filter by is_fraud = true or fraud_score > threshold
- Format timestamp as human-readable date/time
- Include download link or email CSV to customer

### Marketing Angle
**"The only fraud detection tool that makes Google refunds effortless"**
- Competitors block fraud but don't help with refunds
- We capture everything Google needs
- One-click export → paste into Google's form
- Save hours of manual log analysis

---

## Implementation Priority

### P0 (Must Have - Core Functionality):
1. API Gateway with REST API (explicit resources)
2. GoogleAdsTrackingHandler Lambda (responds with 204 in <1s)
3. DynamoDB GSIs for Google Ads (gclid, keyword, target)
4. SNS topic and critical CloudWatch alarms (response time, errors)
5. Basic CloudWatch Logs
6. Input validation and security measures

### P1 (Should Have - Performance):
1. Lambda memory increased to 1024 MB
2. In-memory caching in Lambda code
3. CloudWatch Dashboard for monitoring
4. Lambda reserved concurrency limits

### P2 (Nice to Have - Operations):
1. API Gateway throttling configuration
2. Additional CloudWatch alarms (DynamoDB throttling)
3. Structured logging with request IDs
4. **Google Refund Export Feature** (Dashboard)
   - Query fraudulent clicks by date range and campaign
   - Export to CSV with columns: Date/Time, GCLID, IP, Campaign, Ad Group, Keyword, Placement, Fraud Score
   - Format matches Google's Click Quality Form requirements
   - One-click export for customers to submit refund claims

---

## Files to Create/Modify

### New Files:
1. `src/google_ads_tracking/app.py` - Google Ads tracking handler Lambda
2. `src/google_ads_tracking/requirements.txt` - Lambda dependencies
3. `tests/test_google_ads_tracking.py` - Unit and integration tests

### Modified Files:
1. `template.yaml` - API Gateway, new Lambda, DynamoDB GSIs, CloudWatch alarms, SNS topic
2. `src/orchestrator/feature_extractor.py` - Google-specific features
3. `src/orchestrator/app.py` - Handle limited-signal events
4. `src/storage/dynamodb_utils.py` - Google Ads query functions
5. `README.md` - Documentation update

---

## Additional Notes

**Naming Conventions:**
- Use generic platform names for shared infrastructure
- SNS Topic: `PlatformOpsAlerts`
- API Gateway: `PlatformAPI`
- Stack Name: `platform-fraudguard`
- Rationale: Generic names survive product rebranding and work for entire platform
- Can rename later if/when final product name is decided

**Future Expansion (Phase 2):**
- Custom domain tracking (track.customerdomain.com)
- Real-time blocking with <200ms redirects
- EdgeOptimized API Gateway for global users
- Potentially DynamoDB DAX if needed
- Browser signal collection (IP, user agent, etc.)

**Questions to Resolve:**
1. Confirm DynamoDB table name for environment variables
2. Confirm AWS region for deployment
3. Any existing VPC requirements?
4. Preferred log retention period (default: 7 days)?
5. Email address for SNS topic subscription

---

## Summary

**Build:**
- REST API Gateway with explicit resources (name: `PlatformAPI`)
- New SNS topic: `PlatformOpsAlerts` with email subscription
- GoogleAdsTrackingHandler Lambda (1024 MB, <1s response)
- DynamoDB GSIs: gclid, keyword, target
- CloudWatch alarms for response time and errors
- In-memory caching for fraud rate lookups
- Input validation and security measures

**Optimize:**
- All Lambdas: 1024 MB memory
- Implement caching in Lambda code
- Basic CloudWatch dashboard
- Lambda reserved concurrency limits

**Skip for Now:**
- EdgeOptimized API Gateway
- DynamoDB DAX
- Lambda@Edge

**Performance Target:**
- 204 response in <500ms
- Background fraud detection in <1s
- Zero Google timeouts

