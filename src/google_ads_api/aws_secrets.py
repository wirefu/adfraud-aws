"""
AWS Secrets Manager integration for Google Ads API credentials
Provides secure credential retrieval from AWS Secrets Manager
"""
import json
import os
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError


def get_credentials_from_secrets_manager(
    secret_name: str = "fraudguard/google-ads-api-credentials",
    region_name: str = "us-east-1"
) -> Optional[Dict[str, Any]]:
    """
    Retrieve Google Ads API credentials from AWS Secrets Manager
    
    Args:
        secret_name: Name of the secret in Secrets Manager
        region_name: AWS region where the secret is stored
    
    Returns:
        Dictionary with credentials or None if not found/accessible
    """
    try:
        secrets_client = boto3.client('secretsmanager', region_name=region_name)
        
        response = secrets_client.get_secret_value(SecretId=secret_name)
        
        # Secret can be stored as JSON string or YAML string
        secret_string = response['SecretString']
        
        # Try to parse as JSON first
        try:
            credentials = json.loads(secret_string)
        except json.JSONDecodeError:
            # If not JSON, assume it's YAML format
            import yaml
            credentials = yaml.safe_load(secret_string)
        
        return credentials
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            print(f"Secret '{secret_name}' not found in Secrets Manager")
        elif error_code == 'AccessDeniedException':
            print(f"Access denied to secret '{secret_name}'. Check IAM permissions.")
        else:
            print(f"Error retrieving secret: {e}")
        return None
    
    except Exception as e:
        print(f"Unexpected error retrieving credentials: {e}")
        return None


def get_credentials_from_parameter_store(
    parameter_name: str = "/fraudguard/google-ads/credentials",
    region_name: str = "us-east-1"
) -> Optional[Dict[str, Any]]:
    """
    Retrieve Google Ads API credentials from AWS Systems Manager Parameter Store
    
    Args:
        parameter_name: Name of the parameter in Parameter Store
        region_name: AWS region where the parameter is stored
    
    Returns:
        Dictionary with credentials or None if not found/accessible
    """
    try:
        ssm = boto3.client('ssm', region_name=region_name)
        
        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        
        parameter_value = response['Parameter']['Value']
        
        # Try to parse as JSON first
        try:
            credentials = json.loads(parameter_value)
        except json.JSONDecodeError:
            # If not JSON, assume it's YAML format
            import yaml
            credentials = yaml.safe_load(parameter_value)
        
        return credentials
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ParameterNotFound':
            print(f"Parameter '{parameter_name}' not found in Parameter Store")
        elif error_code == 'AccessDeniedException':
            print(f"Access denied to parameter '{parameter_name}'. Check IAM permissions.")
        else:
            print(f"Error retrieving parameter: {e}")
        return None
    
    except Exception as e:
        print(f"Unexpected error retrieving credentials: {e}")
        return None


def get_credentials_from_env() -> Optional[Dict[str, Any]]:
    """
    Retrieve Google Ads API credentials from environment variables
    
    Returns:
        Dictionary with credentials or None if not all required vars are set
    """
    required_vars = [
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'GOOGLE_ADS_CLIENT_ID',
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN',
        'GOOGLE_ADS_CUSTOMER_ID'
    ]
    
    credentials = {}
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            return None
        # Map env var names to credential keys
        key = var.replace('GOOGLE_ADS_', '').lower()
        credentials[key] = value
    
    # Map customer_id to login_customer_id
    if 'customer_id' in credentials:
        credentials['login_customer_id'] = credentials.pop('customer_id')
    
    return credentials


def get_google_ads_credentials(
    prefer_aws: bool = True,
    secret_name: str = "fraudguard/google-ads-api-credentials",
    parameter_name: str = "/fraudguard/google-ads/credentials"
) -> Optional[Dict[str, Any]]:
    """
    Get Google Ads credentials from multiple sources in order of preference
    
    Priority order (if prefer_aws=True):
    1. AWS Secrets Manager
    2. AWS Parameter Store
    3. Environment variables
    4. Local file (secrets.json or google-ads.yaml)
    
    Priority order (if prefer_aws=False):
    1. Local file (secrets.json)
    2. Environment variables
    3. Local file (google-ads.yaml)
    4. AWS Secrets Manager
    5. AWS Parameter Store
    
    Args:
        prefer_aws: If True, prefer AWS services over local/env
        secret_name: Name of secret in Secrets Manager
        parameter_name: Name of parameter in Parameter Store
    
    Returns:
        Dictionary with credentials or None if not found
    """
    if prefer_aws:
        # Try AWS Secrets Manager first
        credentials = get_credentials_from_secrets_manager(secret_name)
        if credentials:
            return credentials
        
        # Try Parameter Store
        credentials = get_credentials_from_parameter_store(parameter_name)
        if credentials:
            return credentials
        
        # Try environment variables
        credentials = get_credentials_from_env()
        if credentials:
            return credentials
        
        # Try secrets.json (local file)
        credentials = get_credentials_from_secrets_json()
        if credentials:
            return credentials
    else:
        # Try secrets.json first (local file)
        credentials = get_credentials_from_secrets_json()
        if credentials:
            return credentials
        
        # Try environment variables
        credentials = get_credentials_from_env()
        if credentials:
            return credentials
        
        # Try AWS Secrets Manager
        credentials = get_credentials_from_secrets_manager(secret_name)
        if credentials:
            return credentials
        
        # Try Parameter Store
        credentials = get_credentials_from_parameter_store(parameter_name)
        if credentials:
            return credentials
    
    # Last resort: local file (handled by GoogleAdsClient)
    return None


def get_credentials_from_secrets_json(secrets_path: str = "secrets.json") -> Optional[Dict[str, Any]]:
    """
    Retrieve Google Ads API credentials from secrets.json file
    
    Args:
        secrets_path: Path to secrets.json file
    
    Returns:
        Dictionary with credentials or None if not found/accessible
    """
    import os
    
    if not os.path.exists(secrets_path):
        return None
    
    try:
        with open(secrets_path, 'r') as f:
            secrets = json.load(f)
        
        google_ads = secrets.get('google_ads', {})
        
        # Check if all required fields are present and not empty
        required_fields = ['developer_token', 'client_id', 'client_secret', 'refresh_token', 'login_customer_id']
        if not all(google_ads.get(field) for field in required_fields):
            return None
        
        # Return credentials in the format expected
        return {
            'developer_token': google_ads['developer_token'],
            'client_id': google_ads['client_id'],
            'client_secret': google_ads['client_secret'],
            'refresh_token': google_ads['refresh_token'],
            'login_customer_id': google_ads['login_customer_id'],
            'use_proto_plus': google_ads.get('use_proto_plus', True)  # Add required setting
        }
    
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error loading {secrets_path}: {e}")
        return None

