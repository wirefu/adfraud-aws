# Multi-Platform Ad Fraud Detection Architecture

**Version**: 1.0  
**Date**: November 2024  
**Status**: Implemented

---

## Overview

The FraudGuard AI system now supports multiple ad platforms (Google Ads, Meta Ads, LinkedIn Ads, etc.) through a platform abstraction layer. This architecture allows the system to:

1. **Handle platform-specific event formats** while maintaining a unified fraud detection pipeline
2. **Extract platform-specific features** (e.g., GCLID for Google, FBCLID for Meta) while maintaining consistent ML model inputs
3. **Support platforms with limited signals** (no IP, user agent, etc.) like Google Ads parallel tracking
4. **Easily add new platforms** via platform adapters

---

## Architecture Components

### 1. Platform Abstraction Layer (`src/platforms/`)

#### Base Classes (`base.py`)

- **`PlatformType`**: Enum defining supported platforms
- **`PlatformEvent`**: Standardized event structure across all platforms
- **`PlatformFeatures`**: Metadata about available features per platform
- **`AdPlatform`**: Abstract base class for platform adapters

#### Platform Adapters

Each platform has its own adapter implementing the `AdPlatform` interface:

- **`GoogleAdsPlatform`** (`google_ads.py`):
  - Handles Google Ads parallel tracking events
  - Extracts GCLID, keyword, target ID
  - Provides keyword/target fraud rates
  
- **`MetaAdsPlatform`** (`meta_ads.py`):
  - Handles Meta Ads server-side events (Facebook/Instagram)
  - Extracts FBCLID, campaign ID, ad set ID
  - Provides placement fraud rates
  
- **`LinkedInAdsPlatform`** (`linkedin_ads.py`):
  - Handles LinkedIn Ads events
  - Extracts click ID, campaign ID, audience ID
  - Provides audience fraud rates

#### Factory Pattern (`factory.py`)

- **`get_platform_adapter()`**: Creates platform adapter instances
- **`detect_platform_from_event()`**: Auto-detects platform from raw event

---

## Integration with Existing System

### Orchestrator Integration (`src/orchestrator/app.py`)

The orchestrator now uses platform adapters:

```python
# Detect platform and get adapter
platform_type = detect_platform_from_event(body)
platform_adapter = get_platform_adapter(platform_type, source=body.get('source'))

# Parse event using platform adapter
platform_event = platform_adapter.parse_event(body)

# Get context data using platform adapter
context_data = platform_adapter.get_context_data(platform_event, TABLE_NAME)

# Get platform-specific features
platform_features = platform_adapter.extract_platform_features(platform_event, context_data)
```

**Backward Compatibility**: Falls back to legacy Google Ads handling if platform adapter fails.

### Feature Extractor Integration (`src/orchestrator/feature_extractor.py`)

The feature extractor now handles:

- **Limited signals detection**: Uses `is_limited_signals` flag instead of hardcoded `is_google_ads`
- **Platform-specific features**: Extracts platform-specific fraud rates and pattern scores
- **Multi-platform support**: Handles Google Ads, Meta Ads, LinkedIn Ads features

---

## Platform-Specific Features

### Google Ads
- `keyword_fraud_rate`: Historical fraud rate for keyword
- `target_fraud_rate`: Historical fraud rate for target/placement
- `gclid_pattern_score`: GCLID pattern analysis (0.0-1.0)

### Meta Ads
- `placement_fraud_rate`: Historical fraud rate for placement
- `fbclid_pattern_score`: FBCLID pattern analysis (0.0-1.0)
- `is_facebook_placement`: Boolean flag for Facebook placement
- `is_instagram_placement`: Boolean flag for Instagram placement

### LinkedIn Ads
- `audience_fraud_rate`: Historical fraud rate for audience
- `campaign_fraud_rate`: Historical fraud rate for campaign

---

## Adding New Platforms

To add a new platform:

1. **Create platform adapter** (`src/platforms/{platform}_ads.py`):
   ```python
   class NewPlatformAds(AdPlatform):
       @property
       def platform_type(self) -> PlatformType:
           return PlatformType.NEW_PLATFORM_ADS
       
       def parse_event(self, raw_event: Dict[str, Any]) -> PlatformEvent:
           # Parse raw event into PlatformEvent
           pass
       
       def get_context_data(self, event: PlatformEvent, table_name: str) -> Dict[str, Any]:
           # Get platform-specific context data
           pass
       
       def extract_platform_features(self, event: PlatformEvent, context_data: Dict[str, Any]) -> Dict[str, Any]:
           # Extract platform-specific features
           pass
   ```

2. **Register in factory** (`src/platforms/factory.py`):
   ```python
   _PLATFORM_REGISTRY[PlatformType.NEW_PLATFORM_ADS] = NewPlatformAds
   ```

3. **Add PlatformType enum** (`src/platforms/base.py`):
   ```python
   class PlatformType(Enum):
       NEW_PLATFORM_ADS = "new_platform_ads"
   ```

4. **Update feature extractor** (if needed):
   - Add platform-specific feature extraction logic
   - Update feature vector size if adding new features

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Platform Event Sources                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Google Ads    Meta Ads    LinkedIn Ads    Other Platforms │
│  (Parallel)    (SSE)        (API)           (Webhooks)      │
│      │             │            │                │          │
│      └─────────────┴────────────┴────────────────┘          │
│                      │                                        │
│                      ▼                                        │
│            ┌──────────────────┐                              │
│            │ Platform Factory │                              │
│            │  (Auto-detect)   │                              │
│            └────────┬─────────┘                              │
│                     │                                        │
│                     ▼                                        │
│        ┌────────────────────────┐                           │
│        │  Platform Adapter     │                           │
│        │  (Parse & Extract)    │                           │
│        └────────┬───────────────┘                           │
│                 │                                            │
│                 ▼                                            │
│        ┌────────────────────────┐                           │
│        │  Standardized Event    │                           │
│        │  (PlatformEvent)      │                           │
│        └────────┬───────────────┘                           │
└─────────────────┼───────────────────────────────────────────┘
                  │
┌─────────────────┼───────────────────────────────────────────┐
│    Orchestrator │                                             │
├─────────────────┼─────────────────────────────────────────────┤
│                 │                                             │
│                 ▼                                             │
│        ┌────────────────────────┐                           │
│        │  Context Data Fetch    │                           │
│        │  (Platform-specific)  │                           │
│        └────────┬───────────────┘                           │
│                 │                                             │
│                 ▼                                             │
│        ┌────────────────────────┐                           │
│        │  Feature Extraction    │                           │
│        │  (Platform-aware)      │                           │
│        └────────┬───────────────┘                           │
│                 │                                             │
│                 ▼                                             │
│        ┌────────────────────────┐                           │
│        │  ML Model Inference    │                           │
│        │  (SageMaker Endpoint)  │                           │
│        └────────┬───────────────┘                           │
│                 │                                             │
│                 ▼                                             │
│        ┌────────────────────────┐                           │
│        │  Fraud Decision        │                           │
│        └────────────────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

---

## Training Data Considerations

### Multi-Platform Training Data

The training pipeline should include:

1. **Platform identifier**: Add `platform` feature to training data
2. **Platform-specific features**: Include platform-specific fraud rates and pattern scores
3. **Balanced platform distribution**: Ensure training data includes samples from all platforms
4. **Platform-specific validation**: Validate model performance per platform

### Feature Engineering

When preparing training data:

- **Map platform-specific features** to consistent feature vector
- **Handle missing features** for limited-signals platforms (use defaults)
- **Normalize platform-specific identifiers** (GCLID, FBCLID, etc.)

---

## Testing

### Unit Tests

Test each platform adapter:
- Event parsing
- Context data retrieval
- Feature extraction

### Integration Tests

Test end-to-end flow:
- Platform detection
- Event processing
- Feature extraction
- ML inference

### Platform-Specific Tests

Test platform-specific scenarios:
- Limited signals handling
- Platform-specific fraud patterns
- Cross-platform consistency

---

## Future Enhancements

1. **Platform-Specific Models**: Train separate models per platform for better accuracy
2. **Platform-Specific Thresholds**: Adjust fraud thresholds per platform
3. **Platform Analytics**: Track fraud rates and patterns per platform
4. **Real-time Platform Detection**: Auto-detect platform from event patterns
5. **Platform-Specific Rules**: Add platform-specific fraud detection rules

---

## References

- **Platform Adapters**: `src/platforms/`
- **Orchestrator**: `src/orchestrator/app.py`
- **Feature Extractor**: `src/orchestrator/feature_extractor.py`
- **Training PRD**: `docs/DATA_TRAINING_PRD.md`

