# FraudGuard Google Ads Integration Guide

## Product Roadmap

**Phase 1 (MVP):** Google Parallel Tracking - Easy setup, async fraud detection  
**Phase 2 (Premium):** Custom Domain Tracking - Real-time blocking with customer's branded subdomain

## Understanding Google Parallel Tracking (Phase 1)

Google's Parallel Tracking (enabled by default since 2018) allows fraud detection WITHOUT showing a tracking domain in the ad URL.

### How It Works

```
User clicks Google Ad showing nike.com/shoes
  ↓
User lands IMMEDIATELY on nike.com/shoes (no redirect delay)
  ↓
In PARALLEL, Google pings FraudGuard tracking URL in background
  ↓
FraudGuard analyzes click signals
  ↓
If FRAUD detected: Add to exclusion lists for future blocking
```

### Key Benefits
- ✅ User sees only the real destination URL
- ✅ No redirect delay (better user experience)
- ✅ No DNS setup required from customer
- ✅ Easier onboarding
- ❌ Cannot block clicks in real-time (only future prevention)

### Key Trade-off
You detect fraud **after** the user already landed on the page, so you can't block that specific click. However, you build intelligence to prevent future fraud from the same sources.

## Phase 1 Implementation: Parallel Tracking

### 1. Set Up Tracking Template with Parallel Tracking

In Google Ads, Parallel Tracking is enabled by default. You only provide a tracking template - Google handles the rest.

**In Google Ads, customer sets:**
- **Final URL**: `https://nike.com/new-shoes` (This is what user sees and where they land)
- **Tracking Template**: `https://track.fraudguard.io/pt?cid={campaignid}&gclid={gclid}&kw={keyword}`

**What happens:**
1. User clicks ad
2. User immediately goes to `nike.com/new-shoes`
3. Google separately makes a request to your tracking URL in the background

### 2. ValueTrack Parameters for Parallel Tracking

Same Google parameters, but now they're sent to your server async:

- `{campaignid}` - Campaign ID
- `{adgroupid}` - Ad group ID  
- `{keyword}` - Keyword that triggered ad
- `{matchtype}` - Exact, phrase, broad
- `{creative}` - Ad ID
- `{gclid}` - Google Click ID (CRITICAL for tracking)
- `{targetid}` - Target ID for placements/audiences

**Example tracking URL your campaign manager generates:**
```
https://track.fraudguard.io/pt?
  cid={campaignid}&
  gclid={gclid}&
  kw={keyword}&
  aid={adgroupid}&
  target={targetid}
```

Note: We don't need `{lpurl}` in parallel tracking since we're not redirecting.

### 3. FraudGuard Backend for Parallel Tracking

**CRITICAL:** Your endpoint MUST respond within 1 second with a 2xx status code, or Google will timeout and stop sending tracking requests.

```javascript
// Parallel Tracking endpoint
app.get('/pt', async (req, res) => {
  const {
    cid,        // campaign ID
    gclid,      // Google click ID
    kw,         // keyword
    aid,        // ad group ID
    target      // target ID
  } = req.query;
  
  // RESPOND IMMEDIATELY - Required by Google
  res.status(204).send(); // 204 No Content is standard
  
  // Now analyze fraud AFTER responding
  // Use process.nextTick or queue for async processing
  process.nextTick(async () => {
    try {
      // Collect what signals you can
      // Note: You don't have direct access to user's browser
      // Must rely on Google's provided data + historical patterns
      const signals = {
        gclid: gclid,
        campaign_id: cid,
        keyword: kw,
        ad_group_id: aid,
        target_id: target,
        timestamp: Date.now(),
        // Can look up historical fraud patterns by these IDs
      };
      
      // Run fraud detection based on patterns
      const fraudScore = await detectFraudFromGoogleData(signals);
      
      // Log the click
      await logClick({
        campaign_id: cid,
        gclid: gclid,
        fraud_score: fraudScore,
        is_fraud: fraudScore > THRESHOLD,
        ...signals
      });
      
      if (fraudScore > THRESHOLD) {
        // FRAUD DETECTED - Add to exclusion lists
        await addToFraudDatabase({
          gclid: gclid,
          keyword: kw,
          ad_group_id: aid,
          target_id: target,
          fraud_score: fraudScore
        });
        
        // Optional: Trigger Google Ads API to exclude this source
        await excludeFromGoogleAds({
          campaign_id: cid,
          target_id: target // Exclude this placement/audience
        });
      }
    } catch (error) {
      console.error('Fraud detection error:', error);
      // Don't let errors crash the server
    }
  });
});
```

### 4. Fraud Detection Strategy for Parallel Tracking

Since you can't collect real-time browser signals, you rely on:

**Pattern-Based Detection:**
- Historical fraud rates by keyword
- Known fraudulent placement IDs
- Abnormal click patterns (time of day, frequency)
- Geographic anomalies
- Device/browser patterns from Google's data

**Build Intelligence Over Time:**
```javascript
async function detectFraudFromGoogleData(signals) {
  const { keyword, target_id, gclid } = signals;
  
  // Check if this placement/target has high historical fraud
  const targetFraudRate = await getHistoricalFraudRate(target_id);
  
  // Check if this keyword has abnormal click patterns
  const keywordPattern = await getKeywordClickPattern(keyword);
  
  // Check if this gclid shows bot-like behavior
  const gclidBehavior = await analyzeGclidBehavior(gclid);
  
  // ML model combines these signals
  const fraudScore = await mlModel.predict({
    target_fraud_rate: targetFraudRate,
    keyword_pattern: keywordPattern,
    gclid_behavior: gclidBehavior,
    time_of_day: new Date().getHours(),
    // ... more features
  });
  
  return fraudScore;
}
```

### 5. Google Ads API Integration for Automated Exclusions

Once you detect fraud sources, automatically exclude them:

```javascript
const { GoogleAdsApi } = require('google-ads-api');

async function excludeFromGoogleAds({ campaign_id, target_id }) {
  const client = new GoogleAdsApi({
    client_id: process.env.GOOGLE_ADS_CLIENT_ID,
    client_secret: process.env.GOOGLE_ADS_CLIENT_SECRET,
    refresh_token: customerRefreshToken,
  });
  
  const customer = client.Customer({
    customer_id: customerId,
    refresh_token: customerRefreshToken,
  });
  
  // Add to campaign placement exclusion list
  await customer.campaignCriteria.create({
    campaign: `customers/${customerId}/campaigns/${campaign_id}`,
    placement: {
      url: target_id // The placement URL
    },
    negative: true
  });
}
```

## Example Campaign Manager Integration (Phase 1)

Your campaign manager UI should generate parallel tracking URLs:

```javascript
function generateParallelTrackingUrl(campaign) {
  const trackingDomain = 'https://track.fraudguard.io';
  const trackingParams = new URLSearchParams({
    cid: campaign.id,
    gclid: '{gclid}',     // Google replaces this
    kw: '{keyword}',      // Google replaces this
    aid: '{adgroupid}',   // Google replaces this
    target: '{targetid}', // Google replaces this
    src: 'google'
  });
  
  return `${trackingDomain}/pt?${trackingParams.toString()}`;
}

// Customer copies this into Google Ads tracking template field
// Note: No {lpurl} parameter needed for parallel tracking
```

## How Customers Use It (Phase 1)

1. **Customer creates campaign in your Campaign Manager**
2. **Your system generates the parallel tracking template URL**
3. **Customer copies tracking template into Google Ads**
4. **Customer sets their actual landing page as Final URL (what users see)**
5. **Google handles everything:**
   - User sees and lands on Final URL
   - Google pings your tracking URL in background
6. **FraudGuard builds fraud intelligence and exclusion lists over time**

## Testing Before Launch (Phase 1)

```bash
# Test your parallel tracking endpoint
curl -I "https://track.fraudguard.io/pt?cid=test&gclid=test123&kw=test-keyword"

# Should return 204 No Content quickly (< 1 second)
```

**Test checklist:**
- ✅ Endpoint responds in < 1 second
- ✅ Returns 204 status code
- ✅ Async fraud detection processing works
- ✅ Click data is logged correctly
- ✅ Fraud scores are calculated
- ✅ High-fraud sources trigger exclusion logic

## Phase 2: Custom Domain Tracking (Premium Feature)

For customers who want real-time blocking and their own branded tracking domain.

### Architecture

```
User clicks Google Ad showing track.nike.com
  ↓
Click goes to track.nike.com (customer's subdomain → your server)
  ↓
FraudGuard analyzes click in REAL-TIME
  ↓
If VALID: 302 redirect to nike.com/landing-page
If FRAUD: Block or redirect to fraud warning page
```

### Customer Setup Requirements

1. **Customer creates DNS CNAME record:**
   ```
   track.customerdomain.com → tracking.fraudguard.io
   ```

2. **You provision SSL certificate** (automated via Let's Encrypt)

3. **Customer uses custom tracking template:**
   ```
   https://track.customerdomain.com/c?cid={campaignid}&gclid={gclid}&dest={lpurl}
   ```

### Benefits of Custom Domain
- ✅ User sees customer's brand domain in ad
- ✅ Real-time click blocking (not just post-detection)
- ✅ Can collect browser signals (IP, user agent, etc.)
- ✅ Premium positioning vs parallel tracking
- ❌ Requires DNS setup from customer
- ❌ Adds redirect latency (must optimize for speed)

### Implementation

```javascript
// Custom domain endpoint with real-time blocking
app.get('/c', async (req, res) => {
  const hostname = req.hostname; // e.g., "track.nike.com"
  const { cid, gclid, kw, dest } = req.query;
  
  // Look up which customer owns this tracking domain
  const customer = await getCustomerByTrackingDomain(hostname);
  
  if (!customer) {
    return res.status(404).send('Invalid tracking domain');
  }
  
  // Collect REAL-TIME signals (advantage of custom domain)
  const signals = {
    ip: req.ip,
    userAgent: req.headers['user-agent'],
    timestamp: Date.now(),
    referer: req.headers['referer'],
    acceptLanguage: req.headers['accept-language'],
    // ... more browser signals
  };
  
  // Run fraud detection with rich signal data
  const fraudScore = await detectFraudRealtime(signals);
  
  // Log everything
  await logClick({
    customer_id: customer.id,
    campaign_id: cid,
    gclid: gclid,
    fraud_score: fraudScore,
    ...signals
  });
  
  if (fraudScore > THRESHOLD) {
    // FRAUD: Block this specific click
    return res.status(403).send('Invalid traffic detected');
    // Or redirect to customer's fraud warning page
    // return res.redirect(`https://${customer.mainDomain}/invalid-traffic`);
  }
  
  // VALID: redirect to destination
  const decodedUrl = decodeURIComponent(dest);
  res.redirect(302, decodedUrl);
});
```

### Multi-Domain SSL Management

```javascript
// Automated SSL cert provisioning with Let's Encrypt
const acme = require('acme-client');

async function provisionSSLForCustomer(customDomain) {
  const client = new acme.Client({
    directoryUrl: acme.directory.letsencrypt.production,
    accountKey: await acme.crypto.createPrivateKey()
  });
  
  // Create CSR
  const [key, csr] = await acme.crypto.createCsr({
    commonName: customDomain
  });
  
  // Get certificate
  const cert = await client.auto({
    csr: csr,
    email: 'ssl@fraudguard.io',
    termsOfServiceAgreed: true,
    challengeCreateFn: async (authz, challenge, keyAuthorization) => {
      // DNS-01 challenge for wildcard support
      // or HTTP-01 for specific domains
    },
    challengeRemoveFn: async (authz, challenge, keyAuthorization) => {
      // Cleanup
    }
  });
  
  // Store cert in your SSL manager (AWS ACM, etc.)
  await storeCertificate(customDomain, key, cert);
}
```

### Customer Onboarding UI

```javascript
// Campaign Manager shows custom domain setup wizard
const CustomDomainSetup = () => {
  return (
    <div>
      <h2>Premium: Custom Domain Tracking</h2>
      
      <Step number={1}>
        <h3>Create DNS Record</h3>
        <code>
          Type: CNAME<br/>
          Name: track<br/>
          Value: tracking.fraudguard.io<br/>
          TTL: 3600
        </code>
      </Step>
      
      <Step number={2}>
        <h3>Verify DNS</h3>
        <button onClick={verifyDNS}>Check DNS Setup</button>
        {dnsVerified ? "✓ DNS Verified" : "⏳ Waiting for DNS..."}
      </Step>
      
      <Step number={3}>
        <h3>SSL Certificate</h3>
        {sslActive ? "✓ SSL Active" : "⏳ Provisioning SSL..."}
      </Step>
      
      <Step number={4}>
        <h3>Your Tracking Template</h3>
        <code>
          https://track.yourdomain.com/c?cid={campaignid}&gclid={gclid}&dest={lpurl}
        </code>
        <button>Copy to Clipboard</button>
      </Step>
    </div>
  );
};
```

### Performance Requirements

**Critical for custom domain tracking:**
- Response time < 200ms (affects Google Ads Quality Score)
- SSL handshake optimization
- CDN/edge computing for global low latency
- Connection pooling to reduce overhead

```javascript
// Optimize redirect performance
app.use(compression());
app.use((req, res, next) => {
  // Disable unnecessary middleware for /c endpoint
  if (req.path === '/c') {
    return handleClickRedirect(req, res);
  }
  next();
});

// Keep-alive connections
const http = require('http');
const agent = new http.Agent({
  keepAlive: true,
  keepAliveMsecs: 60000
});
```

## Additional Resources

- [Google Ads Tracking Templates Documentation](https://support.google.com/google-ads/answer/6305348)
- [ValueTrack Parameters Reference](https://support.google.com/google-ads/answer/6305348)
- [Google Ads API Documentation](https://developers.google.com/google-ads/api/docs/start)

## Next Steps

### Phase 1 (MVP - Parallel Tracking)
1. ✅ Set up tracking domain with SSL certificate (track.fraudguard.io)
2. ✅ Implement `/pt` endpoint that responds in < 1 second with 204
3. ✅ Build async fraud detection pipeline
4. ✅ Integrate with Campaign Manager UI to generate tracking templates
5. ✅ Test with Google Ads test campaigns
6. ✅ Build customer dashboard showing fraud analytics
7. ✅ (Optional) Integrate Google Ads API for automated exclusions

### Phase 2 (Premium - Custom Domains)
1. 🔲 Build multi-tenant custom domain infrastructure
2. 🔲 Implement automated SSL provisioning (Let's Encrypt)
3. 🔲 Create DNS verification system
4. 🔲 Build customer onboarding wizard for DNS setup
5. 🔲 Implement `/c` endpoint with real-time blocking
6. 🔲 Optimize for < 200ms response times globally
7. 🔲 Add premium tier pricing in Campaign Manager

### Success Metrics to Track
- **Phase 1:** % of fraud detected, exclusion list growth, customer click volume
- **Phase 2:** Adoption rate of custom domains, redirect latency, real-time block rate
