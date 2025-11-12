# Secrets Configuration

This project uses `secrets.json` to store sensitive credentials securely.

## Setup

1. **Copy the example file:**
   ```bash
   cp secrets.json.example secrets.json
   ```

2. **Fill in your credentials:**
   Edit `secrets.json` and add your actual credentials:
   ```json
   {
     "google_ads": {
       "developer_token": "your-actual-token",
       "client_id": "your-client-id.apps.googleusercontent.com",
       "client_secret": "your-client-secret",
       "refresh_token": "your-refresh-token",
       "login_customer_id": "1234567890"
     }
   }
   ```

3. **Security:**
   - ✅ `secrets.json` is already in `.gitignore` - it will never be committed
   - ✅ Keep this file secure and never share it
   - ✅ Use file permissions: `chmod 600 secrets.json`

## File Structure

The `secrets.json` file supports multiple credential types:

```json
{
  "google_ads": {
    "developer_token": "...",
    "client_id": "...",
    "client_secret": "...",
    "refresh_token": "...",
    "login_customer_id": "..."
  },
  "aws": {
    "region": "us-east-1",
    "dynamodb_table_name": "fraudguard-events-dev",
    "s3_bucket_name": ""
  }
}
```

## Credential Priority

The system will look for credentials in this order:

1. **secrets.json** (highest priority for local development)
2. AWS Secrets Manager (for production)
3. AWS Parameter Store
4. Environment variables
5. google-ads.yaml file (fallback)

## Getting Google Ads Credentials

See `GOOGLE_ADS_API_SETUP.md` for detailed instructions on obtaining:
- Developer Token
- OAuth2 Client ID & Secret
- Refresh Token
- Customer ID

