# Quick Setup: Google Ads API Credentials

## What I Need From You

To pull real data from your Google Ads account, I need your credentials. You can provide them in one of these formats:

### Option 1: Credentials File (Recommended)
Create a file called `google-ads.yaml` in the project root with:

```yaml
developer_token: "YOUR_DEVELOPER_TOKEN"
client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret: "YOUR_CLIENT_SECRET"
refresh_token: "YOUR_REFRESH_TOKEN"
login_customer_id: "1234567890"
```

### Option 2: Tell Me What You Have
Just tell me:
- Do you have a Developer Token?
- Do you have OAuth2 credentials (Client ID & Secret)?
- Do you have a Refresh Token?
- What's your Customer ID (10-digit number)?

I can help you get any missing pieces!

## What I've Set Up

✅ Google Ads API client library
✅ Functions to fetch campaigns, performance, keywords, placements
✅ Dashboard integration to show real data
✅ Automatic fallback to mock data if API not configured

## Next Steps

1. **If you have credentials ready**: Place them in `google-ads.yaml` or tell me where they are
2. **If you need help getting credentials**: I can guide you through the OAuth2 flow
3. **Test the connection**: Once configured, the dashboard will automatically use real data

Let me know what format your credentials are in, and I'll help you set them up!
