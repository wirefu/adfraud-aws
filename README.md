# FraudGuard AI - Ad Fraud Detection System

An intelligent ad fraud detection system that combines traditional machine learning with advanced AI analysis to identify and block fraudulent advertising traffic in real-time.

## Architecture

The system uses a two-tier detection approach:
- **Tier 1 (ML)**: Fast XGBoost-based screening for immediate decisions (<100ms)
- **Tier 2 (AI)**: Deep analysis using Amazon Bedrock/Claude for sophisticated fraud patterns (1-3s)

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed (optional, for easier deployment)
- Python 3.11
- AWS Account with permissions for:
  - API Gateway
  - Lambda
  - DynamoDB
  - S3
  - SageMaker
  - Bedrock

## Project Structure

```
.
├── template.yaml          # AWS SAM template
├── samconfig.toml        # SAM configuration
├── docs/                 # Additional documentation
├── src/
│   ├── ingestion/        # Ingestion handler Lambda
│   ├── orchestrator/     # Fraud orchestrator Lambda
│   └── ai_analyzer/      # AI analysis Lambda
└── README.md
```

## Setup

1. **Install AWS SAM CLI** (if not already installed):
   ```bash
   # macOS
   brew install aws-sam-cli
   
   # Or using pip
   pip install aws-sam-cli
   ```

2. **Build the application**:
   ```bash
   sam build
   ```

3. **Deploy to AWS**:
   ```bash
   sam deploy --guided
   ```

4. **Get API endpoint and key**:
   After deployment, check the CloudFormation outputs for:
   - API URL
   - API Key

## Development

### Local Testing

```bash
# Start local API
sam local start-api

# Invoke function locally
sam local invoke IngestionHandler --event events/event.json
```

### Environment Variables

Set up your `.env` file with:
- AWS credentials
- API keys for Bedrock
- Other configuration

## Documentation

Additional documentation is available in the [`/docs`](docs/) folder:

- **Product Requirements**: [`ad-fraud-detection-prd.md`](docs/ad-fraud-detection-prd.md)
- **Integration Guides**: 
  - [`INTEGRATION.md`](docs/INTEGRATION.md)
  - [`fraudguard-google-ads-integration.md`](docs/fraudguard-google-ads-integration.md)
  - [`GOOGLE_ADS_IMPLEMENTATION.md`](docs/GOOGLE_ADS_IMPLEMENTATION.md)
- **Storage**: [`STORAGE.md`](docs/STORAGE.md)
- **Testing**: [`TESTING_BEDROCK.md`](docs/TESTING_BEDROCK.md)
- **Development**: [`BRANCH_STRATEGY.md`](docs/BRANCH_STRATEGY.md)

Module-specific documentation:
- **Dashboard**: [`dashboard/README.md`](dashboard/README.md) and [`dashboard/DEPLOYMENT.md`](dashboard/DEPLOYMENT.md)
- **Scripts**: [`scripts/README.md`](scripts/README.md)
- **Components**: See README files in respective `src/` subdirectories

## Resources

- **API Gateway**: REST API endpoint for fraud detection
- **Lambda Functions**: 
  - Ingestion Handler: Parse and store events
  - Fraud Orchestrator: Route to ML/AI analysis
  - AI Analyzer: Deep fraud analysis using Bedrock
- **DynamoDB**: Real-time event storage
- **S3**: Long-term data storage and training data
- **SageMaker**: XGBoost model endpoint
- **Bedrock**: Claude 3 Sonnet for AI analysis

## Next Steps

1. Implement Lambda functions
2. Train and deploy XGBoost model
3. Configure Bedrock access
4. Build Streamlit dashboard
5. Set up monitoring and alerting

## License

Proprietary - All rights reserved

