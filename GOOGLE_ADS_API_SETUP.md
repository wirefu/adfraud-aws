# Google Ads API Setup Guide

## Prerequisites

1. **Google Ads Account** with API access enabled
2. **Developer Token** from Google Ads
3. **OAuth2 Credentials** from Google Cloud Console
4. **Customer ID** (10-digit Google Ads account ID)

## Step 1: Get Developer Token

1. Go to https://ads.google.com/aw/apicenter
2. Sign in with your Google Ads account
3. Apply for API access (if not already done)
4. Copy your Developer Token

## Step 2: Create OAuth2 Credentials

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable "Google Ads API"
4. Go to "APIs & Services" > "Credentials"
5. Create OAuth 2.0 Client ID
6. Application type: "Desktop app"
7. Download or copy Client ID and Client Secret

## Step 3: Get Refresh Token

Run the OAuth2 flow to get a refresh token:

```bash
python -m google.ads.googleads.oauth2 \
  --client_id=YOUR_CLIENT_ID \
  --client_secret=YOUR_CLIENT_SECRET
```

Follow the prompts to authorize and get your refresh token.

## Step 4: Configure Credentials

1. Copy `google-ads.yaml.example` to `google-ads.yaml`
2. Fill in your credentials:
   - `developer_token`: Your developer token
   - `client_id`: Your OAuth2 client ID
   - `client_secret`: Your OAuth2 client secret
   - `refresh_token`: Your refresh token from Step 3
   - `login_customer_id`: Your 10-digit Google Ads customer ID

## Step 5: Install Dependencies

```bash
cd dashboard
pip install -r requirements.txt
```

Or install globally:
```bash
pip install google-ads>=23.0.0
```

## Step 6: Test Connection

The dashboard will automatically detect and use Google Ads API credentials if available.
You can test the connection by running:

```python
from src.google_ads_api.client import GoogleAdsAPIClient
client = GoogleAdsAPIClient()
campaigns = client.get_campaigns()
print(f"Found {len(campaigns)} campaigns")
```

## Environment Variables (Alternative)

Instead of `google-ads.yaml`, you can set environment variables:

```bash
export GOOGLE_ADS_CREDENTIALS="/path/to/google-ads.yaml"
export GOOGLE_ADS_CUSTOMER_ID="1234567890"
```

## Security Notes

- **Never commit** `google-ads.yaml` to git
- Add `google-ads.yaml` to `.gitignore`
- Use environment variables or secure credential storage in production
- Rotate credentials regularly

