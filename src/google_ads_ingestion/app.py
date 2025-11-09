"""
Google Ads Data Ingestion Lambda Function
Fetches daily Google Ads data and stores in S3 and DynamoDB
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")

# Environment variables
TABLE_NAME = os.environ.get("GOOGLE_ADS_METRICS_TABLE_NAME", "google-ads-metrics-dev")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
SECRETS_NAME = os.environ.get("GOOGLE_ADS_SECRETS_NAME", "fraudguard-ai-dev-google-ads-api-credentials")
CUSTOMER_IDS = os.environ.get("GOOGLE_ADS_CUSTOMER_IDS", "").split(",")  # Comma-separated list

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
BACKOFF_MULTIPLIER = 2


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle EventBridge scheduled trigger for daily Google Ads data ingestion

    Args:
        event: EventBridge event (scheduled trigger)
        context: Lambda context object

    Returns:
        Dictionary with ingestion status and metrics
    """
    start_time = datetime.now(timezone.utc)
    ingestion_date = start_time.strftime("%Y-%m-%d")

    try:
        # Get Google Ads API credentials from Secrets Manager
        credentials = get_google_ads_credentials()

        # Initialize Google Ads client
        google_ads_client = initialize_google_ads_client(credentials)

        # Get customer IDs to process
        customer_ids = get_customer_ids()

        # Process each customer account
        results = []
        for customer_id in customer_ids:
            if not customer_id.strip():
                continue

            try:
                result = ingest_customer_data(google_ads_client, customer_id.strip(), ingestion_date)
                results.append(result)
            except Exception as e:
                print(f"Error processing customer {customer_id}: {str(e)}")
                results.append(
                    {
                        "customer_id": customer_id,
                        "status": "error",
                        "error": str(e),
                    }
                )

        # Calculate total processing time
        processing_time_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "ingestion_date": ingestion_date,
                    "customers_processed": len(results),
                    "results": results,
                    "processing_time_ms": processing_time_ms,
                }
            ),
        }

    except Exception as e:
        print(f"Error in Google Ads ingestion: {str(e)}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "status": "error",
                    "error": str(e),
                    "ingestion_date": ingestion_date,
                }
            ),
        }


def get_google_ads_credentials() -> Dict[str, str]:
    """
    Retrieve Google Ads API credentials from AWS Secrets Manager

    Returns:
        Dictionary with Google Ads API credentials
    """
    try:
        response = secrets_client.get_secret_value(SecretId=SECRETS_NAME)
        secret = json.loads(response["SecretString"])

        required_fields = ["developer_token", "client_id", "client_secret", "refresh_token", "login_customer_id"]
        for field in required_fields:
            if field not in secret:
                raise ValueError(f"Missing required credential field: {field}")

        return secret

    except Exception as e:
        raise Exception(f"Failed to retrieve Google Ads credentials: {str(e)}")


def initialize_google_ads_client(credentials: Dict[str, str]) -> GoogleAdsClient:
    """
    Initialize Google Ads API client

    Args:
        credentials: Google Ads API credentials dictionary

    Returns:
        GoogleAdsClient instance
    """
    try:
        # Create config dictionary for Google Ads client
        config = {
            "developer_token": credentials["developer_token"],
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "refresh_token": credentials["refresh_token"],
            "login_customer_id": credentials["login_customer_id"],
            "use_proto_plus": True,
        }

        # Initialize client with config dictionary
        # Note: GoogleAdsClient.load_from_dict() requires a dict with nested structure
        client_config = {
            "developer_token": config["developer_token"],
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": config["refresh_token"],
            "login_customer_id": config["login_customer_id"],
            "use_proto_plus": config["use_proto_plus"],
        }

        client = GoogleAdsClient.load_from_dict(client_config)

        return client

    except Exception as e:
        raise Exception(f"Failed to initialize Google Ads client: {str(e)}")


def get_customer_ids() -> List[str]:
    """
    Get list of Google Ads customer IDs to process

    Returns:
        List of customer IDs
    """
    if CUSTOMER_IDS and CUSTOMER_IDS[0]:
        return [cid.strip() for cid in CUSTOMER_IDS if cid.strip()]

    # If not provided, try to get from credentials
    credentials = get_google_ads_credentials()
    if "login_customer_id" in credentials:
        return [credentials["login_customer_id"]]

    raise ValueError("No customer IDs provided. Set GOOGLE_ADS_CUSTOMER_IDS environment variable.")


def ingest_customer_data(client: GoogleAdsClient, customer_id: str, ingestion_date: str) -> Dict[str, Any]:
    """
    Ingest data for a single Google Ads customer account

    Args:
        client: GoogleAdsClient instance
        customer_id: Google Ads customer ID
        ingestion_date: Date string in YYYY-MM-DD format

    Returns:
        Dictionary with ingestion results
    """
    print(f"Starting ingestion for customer {customer_id} on {ingestion_date}")

    # Fetch campaign metrics from Google Ads API
    campaign_data = fetch_campaign_metrics(client, customer_id, ingestion_date)

    # Store raw JSON in S3
    s3_key = store_raw_data_in_s3(campaign_data, customer_id, ingestion_date)

    # Aggregate metrics and store in DynamoDB
    metrics_stored = store_metrics_in_dynamodb(campaign_data, customer_id, ingestion_date)

    return {
        "customer_id": customer_id,
        "status": "success",
        "campaigns_processed": len(campaign_data),
        "metrics_stored": metrics_stored,
        "s3_key": s3_key,
    }


def fetch_campaign_metrics(client: GoogleAdsClient, customer_id: str, date: str) -> List[Dict[str, Any]]:
    """
    Fetch campaign metrics from Google Ads API

    Args:
        client: GoogleAdsClient instance
        customer_id: Google Ads customer ID
        date: Date string in YYYY-MM-DD format

    Returns:
        List of campaign metric dictionaries
    """
    # Parse date to get start and end date (same day for daily ingestion)
    # Google Ads API uses YYYY-MM-DD format for dates
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    start_date = date_obj.strftime("%Y-%m-%d")
    end_date = start_date  # Same day for daily ingestion

    # Build GAQL query
    # Note: Google Ads API date format is YYYY-MM-DD
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            segments.date,
            segments.device,
            segments.country_code,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc,
            metrics.search_impression_share,
            metrics.quality_score,
            metrics.invalid_clicks,
            metrics.invalid_click_rate
        FROM campaign
        WHERE segments.date = '{start_date}'
            AND campaign.status != 'REMOVED'
        ORDER BY campaign.id, segments.date, segments.device, segments.country_code
    """

    campaign_data = []
    retries = 0

    while retries < MAX_RETRIES:
        try:
            # Execute query
            ga_service = client.get_service("GoogleAdsService")
            response = ga_service.search(customer_id=customer_id, query=query)

            # Process results
            for row in response:
                campaign_metric = {
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": row.campaign.name,
                    "campaign_status": row.campaign.status.name,
                    "advertising_channel_type": row.campaign.advertising_channel_type.name,
                    "date": row.segments.date,
                    "device": row.segments.device.name if row.segments.device else None,
                    "country_code": row.segments.country_code if row.segments.country_code else None,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "cost_micros": row.metrics.cost_micros,
                    "conversions": row.metrics.conversions,
                    "conversions_value": row.metrics.conversions_value,
                    "ctr": row.metrics.ctr,
                    "average_cpc_micros": row.metrics.average_cpc,
                    "search_impression_share": row.metrics.search_impression_share,
                    "quality_score": row.metrics.quality_score if hasattr(row.metrics, "quality_score") else None,
                    "invalid_clicks": row.metrics.invalid_clicks,
                    "invalid_click_rate": row.metrics.invalid_click_rate,
                }

                campaign_data.append(campaign_metric)

            # Success - break retry loop
            break

        except GoogleAdsException as e:
            # Check if it's a rate limit error
            if "RATE_EXCEEDED" in str(e) or "429" in str(e):
                retries += 1
                if retries < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (BACKOFF_MULTIPLIER ** (retries - 1))
                    print(f"Rate limit exceeded. Retrying in {wait_time} seconds... (attempt {retries}/{MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Rate limit exceeded after {MAX_RETRIES} retries: {str(e)}")
            else:
                raise Exception(f"Google Ads API error: {str(e)}")

        except Exception as e:
            raise Exception(f"Error fetching campaign metrics: {str(e)}")

    return campaign_data


def store_raw_data_in_s3(data: List[Dict[str, Any]], customer_id: str, date: str) -> str:
    """
    Store raw campaign data in S3 with date partitioning

    Args:
        data: List of campaign metric dictionaries
        customer_id: Google Ads customer ID
        date: Date string in YYYY-MM-DD format

    Returns:
        S3 key where data was stored
    """
    if not BUCKET_NAME:
        raise ValueError("S3_BUCKET_NAME environment variable not set")

    # Create S3 key with date partitioning
    s3_key = f"google-ads/raw-data/date={date}/customer_id={customer_id}/campaign_metrics.json"

    # Store as JSON
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(data, default=str),
        ContentType="application/json",
        Metadata={
            "customer_id": customer_id,
            "date": date,
            "campaigns_count": str(len(data)),
        },
    )

    return s3_key


def store_metrics_in_dynamodb(campaign_data: List[Dict[str, Any]], customer_id: str, date: str) -> int:
    """
    Aggregate and store campaign metrics in DynamoDB

    Args:
        campaign_data: List of campaign metric dictionaries
        customer_id: Google Ads customer ID
        date: Date string in YYYY-MM-DD format

    Returns:
        Number of metrics stored
    """
    if not TABLE_NAME:
        raise ValueError("GOOGLE_ADS_METRICS_TABLE_NAME environment variable not set")

    table = dynamodb.Table(TABLE_NAME)
    metrics_stored = 0

    # Group by campaign_id (aggregate across all devices and countries)
    aggregated_metrics = {}

    for metric in campaign_data:
        campaign_id = metric["campaign_id"]

        if campaign_id not in aggregated_metrics:
            aggregated_metrics[campaign_id] = {
                "campaign_id": campaign_id,
                "campaign_name": metric["campaign_name"],
                "campaign_status": metric["campaign_status"],
                "advertising_channel_type": metric["advertising_channel_type"],
                "date": date,
                "impressions": 0,
                "clicks": 0,
                "cost_micros": 0,
                "conversions": 0.0,
                "conversions_value": 0.0,
                "invalid_clicks": 0,
                "devices": set(),  # Track unique devices
                "countries": set(),  # Track unique countries
            }

        # Aggregate metrics
        agg = aggregated_metrics[campaign_id]
        agg["impressions"] += metric["impressions"]
        agg["clicks"] += metric["clicks"]
        agg["cost_micros"] += metric["cost_micros"]
        agg["conversions"] += metric["conversions"]
        agg["conversions_value"] += metric["conversions_value"]
        agg["invalid_clicks"] += metric["invalid_clicks"]

        # Track devices and countries
        if metric.get("device"):
            agg["devices"].add(metric["device"])
        if metric.get("country_code"):
            agg["countries"].add(metric["country_code"])

    # Calculate derived metrics and store in DynamoDB
    for campaign_id, agg in aggregated_metrics.items():
        # Calculate derived metrics
        cost = agg["cost_micros"] / 1_000_000  # Convert micros to dollars
        ctr = (agg["clicks"] / agg["impressions"]) * 100 if agg["impressions"] > 0 else 0.0
        conversion_rate = (agg["conversions"] / agg["clicks"]) * 100 if agg["clicks"] > 0 else 0.0
        cpa = cost / agg["conversions"] if agg["conversions"] > 0 else 0.0
        roas = agg["conversions_value"] / cost if cost > 0 else 0.0
        avg_cpc = cost / agg["clicks"] if agg["clicks"] > 0 else 0.0
        invalid_click_rate = (agg["invalid_clicks"] / agg["clicks"]) * 100 if agg["clicks"] > 0 else 0.0

        # Get primary device and country (most common, or first if multiple)
        primary_device = list(agg["devices"])[0] if agg["devices"] else None
        primary_country = list(agg["countries"])[0] if agg["countries"] else None

        # Create DynamoDB item
        item = {
            "pk": f"CAMPAIGN#{campaign_id}",
            "sk": f"DATE#{date}",
            "ttl": int((datetime.strptime(date, "%Y-%m-%d") + timedelta(days=30)).timestamp()),
            "campaign_id": campaign_id,
            "campaign_name": agg["campaign_name"],
            "campaign_status": agg["campaign_status"],
            "advertising_channel_type": agg["advertising_channel_type"],
            "date": date,
            "impressions": agg["impressions"],
            "clicks": agg["clicks"],
            "cost": Decimal(str(cost)),
            "conversions": Decimal(str(agg["conversions"])),
            "conversion_value": Decimal(str(agg["conversions_value"])),
            "ctr": Decimal(str(ctr)),
            "conversion_rate": Decimal(str(conversion_rate)),
            "cpa": Decimal(str(cpa)),
            "roas": Decimal(str(roas)),
            "avg_cpc": Decimal(str(avg_cpc)),
            "device": primary_device,
            "country_code": primary_country,
            "invalid_clicks": agg["invalid_clicks"],
            "invalid_click_rate": Decimal(str(invalid_click_rate)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in DynamoDB
        table.put_item(Item=item)
        metrics_stored += 1

    return metrics_stored


def convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

