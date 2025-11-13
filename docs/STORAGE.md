# Storage Architecture

This document describes the DynamoDB and S3 storage architecture for FraudGuard AI.

## DynamoDB Table: `fraudguard-events`

### Schema

**Primary Key:**
- Partition Key: `event_id` (String)
- Sort Key: `timestamp` (Number - Unix epoch)

**Attributes:**
- `event_id` (String) - Unique event identifier
- `timestamp` (Number) - Unix epoch timestamp
- `event_type` (String) - click, impression, install, conversion
- `ip_address` (String) - IP address of the event
- `user_agent` (String) - User agent string
- `device_id` (String) - Device identifier
- `campaign_id` (String) - Campaign identifier
- `publisher_id` (String) - Publisher identifier
- `referrer` (String) - Referrer URL
- `click_id` (String) - Click identifier
- `ml_score` (Number) - ML fraud score (0.0-1.0)
- `ai_score` (Number, nullable) - AI fraud score (0.0-1.0)
- `is_fraud` (Boolean) - Fraud verdict
- `fraud_signals` (StringSet) - List of fraud signals
- `reasoning` (String, nullable) - AI reasoning explanation
- `detection_method` (String) - ml_only, ml_ai_ensemble
- `fraud_result` (Map) - Complete fraud detection result
- `ttl` (Number) - Time to live (7 days from creation)
- `created_at` (String) - ISO timestamp
- `updated_at` (String) - ISO timestamp

**Global Secondary Indexes:**

1. **campaign-timestamp-index**
   - Partition Key: `campaign_id` (String)
   - Sort Key: `timestamp` (Number)
   - Projection: ALL
   - Purpose: Query events by campaign and time range

2. **device-timestamp-index**
   - Partition Key: `device_id` (String)
   - Sort Key: `timestamp` (Number)
   - Projection: ALL
   - Purpose: Query events by device and time range

**Features:**
- Billing Mode: PAY_PER_REQUEST (on-demand)
- Time to Live (TTL): Enabled on `ttl` attribute (7 days)
- Point-in-Time Recovery: Enabled
- Streams: Enabled (NEW_AND_OLD_IMAGES)

## S3 Bucket: `fraudguard-data-{account-id}-{region}`

### Structure

```
s3://fraudguard-data-{account-id}-{region}/
├── raw-events/
│   └── date=2025-11-05/
│       └── hour=14/
│           └── {event_id}.json
├── training-data/
│   └── v1.0/
│       ├── features_20251105.json
│       └── labels_20251105.json
└── models/
    └── xgboost-v1.0/
        └── model.tar.gz
```

### Lifecycle Policies

1. **Archive to Glacier after 90 days**
   - Applies to: `raw-events/`
   - Transition: Standard → Glacier after 90 days

2. **Delete old versions**
   - Non-current versions → Glacier IR after 30 days
   - Non-current versions expire after 90 days

### Security

- **Encryption**: AES256 server-side encryption
- **Public Access**: Blocked (all public access blocked)
- **Secure Transport**: Required (HTTPS only)
- **Versioning**: Enabled

## Data Flow

### Real-Time Storage

1. **Ingestion Handler** receives event
2. Stores enriched event in **DynamoDB** (hot storage)
3. Stores raw event in **S3** (cold storage) with date partitioning
4. DynamoDB TTL automatically deletes events after 7 days

### Query Patterns

1. **By Event ID**: Direct DynamoDB query using primary key
2. **By Campaign**: Query using `campaign-timestamp-index` GSI
3. **By Device**: Query using `device-timestamp-index` GSI
4. **Historical Analysis**: Query S3 by date range

### Cost Optimization

- **DynamoDB**: On-demand pricing (pay per request)
- **S3**: Lifecycle policies to archive old data to Glacier
- **TTL**: Automatic cleanup of old data from DynamoDB
- **Partitioning**: Efficient S3 queries by date/hour

## Access Patterns

### Write Patterns

- **High frequency**: Real-time event ingestion
- **Low latency**: <10ms DynamoDB writes
- **Durability**: 99.999999999% (S3 standard)

### Read Patterns

- **Real-time queries**: DynamoDB (last 7 days)
- **Historical queries**: S3 (all historical data)
- **Analytics**: S3 Parquet format for efficient querying

## Testing

### DynamoDB Testing

```bash
# Create test event
aws dynamodb put-item \
  --table-name fraudguard-events \
  --item '{
    "event_id": {"S": "test-123"},
    "timestamp": {"N": "1234567890"},
    "event_type": {"S": "click"}
  }'

# Query by campaign
aws dynamodb query \
  --table-name fraudguard-events \
  --index-name campaign-timestamp-index \
  --key-condition-expression "campaign_id = :cid" \
  --expression-attribute-values '{":cid": {"S": "campaign-456"}}'
```

### S3 Testing

```bash
# List events for a date
aws s3 ls s3://fraudguard-data-{account-id}-{region}/raw-events/date=2025-11-05/

# Get event
aws s3 cp s3://fraudguard-data-{account-id}-{region}/raw-events/date=2025-11-05/hour=14/{event_id}.json -
```

