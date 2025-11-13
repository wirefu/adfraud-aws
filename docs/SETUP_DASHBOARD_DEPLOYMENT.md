# Dashboard Deployment Setup Guide

This guide walks you through setting up the ECR repository and GitHub secrets needed for automated dashboard deployment.

## Quick Start

### 1. Create ECR Repository

Run the setup script:
```bash
cd scripts
chmod +x setup_ecr.sh
./setup_ecr.sh
```

Or manually:
```bash
aws ecr create-repository \
  --repository-name fraudguard-dashboard \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=AES256
```

### 2. Configure GitHub Secrets

#### Option A: Using GitHub CLI (Recommended)

```bash
cd scripts
chmod +x setup_github_secrets.sh
./setup_github_secrets.sh
```

#### Option B: Manual Setup via GitHub Web UI

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

**Required:**
- `AWS_ACCESS_KEY_ID` - Your AWS access key ID
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret access key

**Optional:**
- `APP_RUNNER_AUTO_SCALING_ARN` - App Runner auto-scaling configuration ARN

#### Option C: Using GitHub CLI Manually

```bash
# Set AWS credentials
gh secret set AWS_ACCESS_KEY_ID --body "YOUR_ACCESS_KEY_ID"
gh secret set AWS_SECRET_ACCESS_KEY --body "YOUR_SECRET_ACCESS_KEY"

# Optional: Set auto-scaling ARN
gh secret set APP_RUNNER_AUTO_SCALING_ARN --body "YOUR_AUTO_SCALING_ARN"
```

### 3. Create IAM User for GitHub Actions

Create an IAM user with the following permissions:

```bash
# Create user
aws iam create-user --user-name github-actions-dashboard-deploy

# Create access key
aws iam create-access-key --user-name github-actions-dashboard-deploy
# Save the AccessKeyId and SecretAccessKey for GitHub secrets

# Create and attach policy (see scripts/setup_dashboard_deployment.md for full policy)
```

## Detailed Instructions

See `scripts/setup_dashboard_deployment.md` for complete setup instructions including:
- IAM policy creation
- Environment configuration
- Troubleshooting
- Verification checklist

## Verification

After setup, test the deployment:

1. Make a change to `dashboard/app.py`
2. Commit and push to `main` or `develop`
3. Check GitHub Actions tab for workflow execution
4. Verify deployment in AWS App Runner console

## Troubleshooting

### ECR Repository Not Found
```bash
./scripts/setup_ecr.sh
```

### Access Denied
- Verify IAM user has correct permissions
- Check AWS credentials in GitHub secrets

### GitHub Secrets Not Working
- Verify secrets are set in the correct repository
- Check secret names match workflow expectations

## Next Steps

1. ✅ Complete setup (ECR + GitHub secrets)
2. ✅ Test deployment workflow
3. ✅ Monitor first deployment
4. ✅ Verify dashboard accessibility

