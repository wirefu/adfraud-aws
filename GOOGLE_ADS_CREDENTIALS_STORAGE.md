# Secure Storage Options for Google Ads API Credentials

## 🔒 Security Best Practices

**Never commit credentials to git!** All credential files are already in `.gitignore`.

## Storage Options (Ranked by Security)

### 1. 🏆 AWS Secrets Manager (Recommended for Production)

**Best for:** Production deployments, AWS Lambda, ECS tasks

**Pros:**
- ✅ Encrypted at rest and in transit
- ✅ Automatic rotation support
- ✅ Fine-grained access control via IAM
- ✅ Audit logging via CloudTrail
- ✅ Versioning and recovery
- ✅ No credentials in code or environment

**Setup:**

```bash
# Store credentials in AWS Secrets Manager
aws secretsmanager create-secret \
  --name fraudguard/google-ads-api-credentials \
  --description "Google Ads API credentials for FraudGuard" \
  --secret-string file://google-ads.yaml \
  --region us-east-1

# Or store as JSON
aws secretsmanager create-secret \
  --name fraudguard/google-ads-api-credentials \
  --secret-string '{
    "developer_token": "YOUR_TOKEN",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "login_customer_id": "1234567890"
  }' \
  --region us-east-1
```

**Retrieve in code:**
```python
import boto3
import json

secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
response = secrets_client.get_secret_value(SecretId='fraudguard/google-ads-api-credentials')
credentials = json.loads(response['SecretString'])
```

**IAM Policy Required:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:fraudguard/google-ads-api-credentials-*"
    }
  ]
}
```

---

### 2. 🔐 AWS Systems Manager Parameter Store (Alternative AWS Option)

**Best for:** Simple key-value storage, lower cost than Secrets Manager

**Pros:**
- ✅ Encrypted with KMS
- ✅ IAM access control
- ✅ Free for standard parameters
- ✅ Versioning support
- ✅ Simple API

**Setup:**

```bash
# Store as SecureString (encrypted)
aws ssm put-parameter \
  --name /fraudguard/google-ads/developer_token \
  --value "YOUR_TOKEN" \
  --type SecureString \
  --region us-east-1

aws ssm put-parameter \
  --name /fraudguard/google-ads/client_id \
  --value "YOUR_CLIENT_ID" \
  --type SecureString \
  --region us-east-1

# ... repeat for each credential
```

**Or store entire config as JSON:**
```bash
aws ssm put-parameter \
  --name /fraudguard/google-ads/credentials \
  --value file://google-ads.yaml \
  --type SecureString \
  --region us-east-1
```

**Retrieve in code:**
```python
import boto3

ssm = boto3.client('ssm', region_name='us-east-1')
response = ssm.get_parameter(
    Name='/fraudguard/google-ads/credentials',
    WithDecryption=True
)
credentials_yaml = response['Parameter']['Value']
```

---

### 3. 📁 Local File (For Development Only)

**Best for:** Local development, testing

**Pros:**
- ✅ Simple and fast
- ✅ No AWS setup needed
- ✅ Easy to update

**Cons:**
- ⚠️ Not encrypted (unless you encrypt the file)
- ⚠️ Only secure if your machine is secure
- ⚠️ Not suitable for production

**Setup:**
1. Copy `google-ads.yaml.example` to `google-ads.yaml`
2. Fill in your credentials
3. File is already in `.gitignore` ✅

**Location:** Project root (`/Users/yan/gauntlet/adfraud-aws/google-ads.yaml`)

---

### 4. 🌍 Environment Variables (For Containers/ECS)

**Best for:** Docker containers, ECS tasks, local development

**Pros:**
- ✅ Easy to configure in containers
- ✅ No file management
- ✅ Works with ECS task definitions

**Cons:**
- ⚠️ Visible in process list
- ⚠️ Can leak in logs if not careful
- ⚠️ Not encrypted at rest

**Setup:**

```bash
# Local development
export GOOGLE_ADS_DEVELOPER_TOKEN="YOUR_TOKEN"
export GOOGLE_ADS_CLIENT_ID="YOUR_CLIENT_ID"
export GOOGLE_ADS_CLIENT_SECRET="YOUR_CLIENT_SECRET"
export GOOGLE_ADS_REFRESH_TOKEN="YOUR_REFRESH_TOKEN"
export GOOGLE_ADS_CUSTOMER_ID="1234567890"
```

**Or use .env file (already in .gitignore):**
```bash
# .env
GOOGLE_ADS_DEVELOPER_TOKEN=YOUR_TOKEN
GOOGLE_ADS_CLIENT_ID=YOUR_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET=YOUR_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN=YOUR_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID=1234567890
```

**For ECS Task Definition:**
```json
{
  "containerDefinitions": [{
    "secrets": [
      {
        "name": "GOOGLE_ADS_DEVELOPER_TOKEN",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:fraudguard/google-ads-api-credentials:developer_token::"
      }
    ]
  }]
}
```

---

### 5. 🔑 Encrypted Local File (Extra Security for Local Dev)

**Best for:** Local development with extra security

**Setup:**

```bash
# Encrypt credentials file
gpg --symmetric --cipher-algo AES256 google-ads.yaml
# Creates google-ads.yaml.gpg

# Decrypt when needed
gpg --decrypt google-ads.yaml.gpg > google-ads.yaml
```

**Or use age (modern alternative):**
```bash
# Encrypt
age -e -r age1yourpublickey google-ads.yaml > google-ads.yaml.age

# Decrypt
age -d -i ~/.age-key google-ads.yaml.age > google-ads.yaml
```

---

## Recommended Setup by Environment

### Local Development
- **Option:** Local file (`google-ads.yaml`)
- **Location:** Project root
- **Security:** Ensure file permissions: `chmod 600 google-ads.yaml`

### AWS Lambda Functions
- **Option:** AWS Secrets Manager
- **Why:** Automatic credential injection, encrypted, IAM-controlled

### ECS Dashboard Container
- **Option:** AWS Secrets Manager via ECS secrets
- **Why:** Secure, no credentials in task definition

### CI/CD Pipelines
- **Option:** GitHub Secrets (for GitHub Actions) or AWS Secrets Manager
- **Why:** No credentials in code or logs

---

## Quick Setup Script

I can create a helper script to store credentials in AWS Secrets Manager. Would you like me to create it?

```bash
# Example usage
./scripts/store_google_ads_credentials.sh
```

This would:
1. Read your `google-ads.yaml` file
2. Store it in AWS Secrets Manager
3. Set up IAM permissions
4. Update your code to use Secrets Manager

---

## Migration Guide

### From Local File to AWS Secrets Manager

1. **Store credentials:**
   ```bash
   aws secretsmanager create-secret \
     --name fraudguard/google-ads-api-credentials \
     --secret-string file://google-ads.yaml
   ```

2. **Update code** to use Secrets Manager (I can help with this)

3. **Delete local file** (optional, but recommended):
   ```bash
   rm google-ads.yaml
   ```

4. **Test** that credentials are retrieved correctly

---

## Security Checklist

- [ ] Credentials file is in `.gitignore` ✅
- [ ] File permissions set to 600 (if using local file)
- [ ] AWS Secrets Manager uses encryption ✅
- [ ] IAM policies restrict access to specific roles/users
- [ ] Credentials are rotated regularly
- [ ] No credentials in code, logs, or environment variables (unless encrypted)
- [ ] Audit logging enabled (CloudTrail for AWS)

---

## Need Help?

Tell me which option you prefer, and I'll:
1. Set up the storage method
2. Update the code to retrieve credentials securely
3. Create helper scripts for easy management
4. Configure IAM permissions if using AWS

