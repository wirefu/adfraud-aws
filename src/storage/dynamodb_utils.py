"""
DynamoDB utility functions for event storage and retrieval
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
import os

# Get region from environment or default to us-east-1
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def get_table(table_name: str):
    """
    Get DynamoDB table resource

    Args:
        table_name: Name of the DynamoDB table

    Returns:
        DynamoDB table resource
    """
    return dynamodb.Table(table_name)


def store_event(table_name: str, event: Dict[str, Any]) -> None:
    """
    Store event in DynamoDB

    Args:
        table_name: Name of the DynamoDB table
        event: Event dictionary to store
    """
    table = get_table(table_name)

    # Convert floats to Decimal for DynamoDB
    event = convert_floats_to_decimal(event)

    table.put_item(Item=event)


def get_event(table_name: str, event_id: str) -> Optional[Dict[str, Any]]:
    """
    Get event by event_id

    Args:
        table_name: Name of the DynamoDB table
        event_id: Event ID to retrieve

    Returns:
        Event dictionary or None if not found
    """
    table = get_table(table_name)

    try:
        response = table.get_item(Key={"event_id": event_id})
        return response.get("Item")
    except Exception as e:
        print(f"Error getting event: {str(e)}")
        return None


def query_events_by_campaign(
    table_name: str, campaign_id: str, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query events by campaign_id using GSI

    Args:
        table_name: Name of the DynamoDB table
        campaign_id: Campaign ID to query
        start_timestamp: Start timestamp (Unix epoch)
        end_timestamp: End timestamp (Unix epoch)

    Returns:
        List of event dictionaries
    """
    table = get_table(table_name)

    key_condition = "campaign_id = :campaign_id"
    expression_values = {":campaign_id": campaign_id}

    if start_timestamp and end_timestamp:
        key_condition += " AND timestamp BETWEEN :start AND :end"
        expression_values[":start"] = start_timestamp
        expression_values[":end"] = end_timestamp

    try:
        response = table.query(
            IndexName="campaign-timestamp-index",
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values,
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"Error querying events by campaign: {str(e)}")
        return []


def query_events_by_device(
    table_name: str, device_id: str, start_timestamp: Optional[int] = None, end_timestamp: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query events by device_id using GSI

    Args:
        table_name: Name of the DynamoDB table
        device_id: Device ID to query
        start_timestamp: Start timestamp (Unix epoch)
        end_timestamp: End timestamp (Unix epoch)

    Returns:
        List of event dictionaries
    """
    table = get_table(table_name)

    key_condition = "device_id = :device_id"
    expression_values = {":device_id": device_id}

    if start_timestamp and end_timestamp:
        key_condition += " AND timestamp BETWEEN :start AND :end"
        expression_values[":start"] = start_timestamp
        expression_values[":end"] = end_timestamp

    try:
        response = table.query(
            IndexName="device-timestamp-index",
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values,
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"Error querying events by device: {str(e)}")
        return []


def get_ip_click_count_24h(table_name: str, ip_address: str) -> int:
    """
    Get click count for IP address in last 24 hours

    Args:
        table_name: Name of the DynamoDB table
        ip_address: IP address to query

    Returns:
        Click count in last 24 hours
    """
    # TODO: Implement efficient query for IP click count
    # This would require a GSI on ip_address + timestamp
    # For now, return placeholder
    return 0


def get_device_click_count_1h(table_name: str, device_id: str) -> int:
    """
    Get click count for device in last 1 hour

    Args:
        table_name: Name of the DynamoDB table
        device_id: Device ID to query

    Returns:
        Click count in last 1 hour
    """
    now = datetime.now(timezone.utc)
    one_hour_ago = int((now - timedelta(hours=1)).timestamp())
    now_timestamp = int(now.timestamp())

    events = query_events_by_device(table_name, device_id, one_hour_ago, now_timestamp)
    return len(events)


def get_time_since_last_click(table_name: str, device_id: str) -> Optional[int]:
    """
    Get time since last click for device

    Args:
        table_name: Name of the DynamoDB table
        device_id: Device ID to query

    Returns:
        Seconds since last click, or None if no previous clicks
    """
    now = datetime.now(timezone.utc)
    one_day_ago = int((now - timedelta(days=1)).timestamp())
    now_timestamp = int(now.timestamp())

    events = query_events_by_device(table_name, device_id, one_day_ago, now_timestamp)

    if not events:
        return None

    # Sort by timestamp descending
    events.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    last_click_timestamp = events[0].get("timestamp", 0)

    return now_timestamp - last_click_timestamp


def query_events_by_gclid(
    table_name: str,
    gclid: str,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query events by gclid using GSI
    
    Args:
        table_name: Name of the DynamoDB table
        gclid: Google Click ID to query
        start_timestamp: Start timestamp (Unix epoch)
        end_timestamp: End timestamp (Unix epoch)
        
    Returns:
        List of event dictionaries
    """
    if not gclid:
        return []
    
    table = get_table(table_name)
    
    key_condition = 'gclid = :gclid'
    expression_values = {':gclid': gclid}
    
    if start_timestamp and end_timestamp:
        key_condition += ' AND timestamp BETWEEN :start AND :end'
        expression_values[':start'] = start_timestamp
        expression_values[':end'] = end_timestamp
    
    try:
        response = table.query(
            IndexName='gclid-timestamp-index',
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying events by gclid: {str(e)}")
        return []


def query_events_by_keyword(
    table_name: str,
    keyword: str,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query events by keyword using GSI
    
    Args:
        table_name: Name of the DynamoDB table
        keyword: Keyword to query
        start_timestamp: Start timestamp (Unix epoch)
        end_timestamp: End timestamp (Unix epoch)
        
    Returns:
        List of event dictionaries
    """
    if not keyword:
        return []
    
    table = get_table(table_name)
    
    key_condition = 'keyword = :keyword'
    expression_values = {':keyword': keyword}
    
    if start_timestamp and end_timestamp:
        key_condition += ' AND timestamp BETWEEN :start AND :end'
        expression_values[':start'] = start_timestamp
        expression_values[':end'] = end_timestamp
    
    try:
        response = table.query(
            IndexName='keyword-timestamp-index',
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying events by keyword: {str(e)}")
        return []


def query_events_by_target(
    table_name: str,
    target_id: str,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query events by target_id using GSI
    
    Args:
        table_name: Name of the DynamoDB table
        target_id: Target ID to query
        start_timestamp: Start timestamp (Unix epoch)
        end_timestamp: End timestamp (Unix epoch)
        
    Returns:
        List of event dictionaries
    """
    if not target_id:
        return []
    
    table = get_table(table_name)
    
    key_condition = 'target_id = :target_id'
    expression_values = {':target_id': target_id}
    
    if start_timestamp and end_timestamp:
        key_condition += ' AND timestamp BETWEEN :start AND :end'
        expression_values[':start'] = start_timestamp
        expression_values[':end'] = end_timestamp
    
    try:
        response = table.query(
            IndexName='target-timestamp-index',
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying events by target: {str(e)}")
        return []


def get_keyword_fraud_rate(table_name: str, keyword: str, days: int = 30) -> float:
    """
    Calculate historical fraud rate for keyword
    
    Args:
        table_name: Name of the DynamoDB table
        keyword: Keyword to analyze
        days: Number of days to look back
        
    Returns:
        Fraud rate (0.0-1.0)
    """
    if not keyword:
        return 0.0
    
    now = datetime.now(timezone.utc)
    start_timestamp = int((now - timedelta(days=days)).timestamp())
    end_timestamp = int(now.timestamp())
    
    events = query_events_by_keyword(table_name, keyword, start_timestamp, end_timestamp)
    
    if not events:
        return 0.0
    
    fraud_count = sum(1 for e in events if e.get('is_fraud', False) or e.get('fraud_score', 0) > 0.65)
    return fraud_count / len(events)


def get_target_fraud_rate(table_name: str, target_id: str, days: int = 30) -> float:
    """
    Calculate historical fraud rate for target/placement
    
    Args:
        table_name: Name of the DynamoDB table
        target_id: Target ID to analyze
        days: Number of days to look back
        
    Returns:
        Fraud rate (0.0-1.0)
    """
    if not target_id:
        return 0.0
    
    now = datetime.now(timezone.utc)
    start_timestamp = int((now - timedelta(days=days)).timestamp())
    end_timestamp = int(now.timestamp())
    
    events = query_events_by_target(table_name, target_id, start_timestamp, end_timestamp)
    
    if not events:
        return 0.0
    
    fraud_count = sum(1 for e in events if e.get('is_fraud', False) or e.get('fraud_score', 0) > 0.65)
    return fraud_count / len(events)


def update_event_result(
    table_name: str,
    event_id: str,
    fraud_result: Dict[str, Any]
) -> None:
    """
    Update event with fraud detection result

    Args:
        table_name: Name of the DynamoDB table
        event_id: Event ID to update
        fraud_result: Fraud detection result dictionary
    """
    table = get_table(table_name)

    # Convert floats to Decimal
    fraud_result = convert_floats_to_decimal(fraud_result)

    update_expression = "SET fraud_result = :result, updated_at = :timestamp"
    expression_values = {":result": fraud_result, ":timestamp": datetime.now(timezone.utc).isoformat()}

    # Add individual fields for easier querying
    if "is_fraud" in fraud_result:
        update_expression += ", is_fraud = :is_fraud"
        expression_values[":is_fraud"] = fraud_result["is_fraud"]

    if "fraud_score" in fraud_result:
        update_expression += ", fraud_score = :fraud_score"
        expression_values[":fraud_score"] = fraud_result["fraud_score"]

    if "ml_score" in fraud_result:
        update_expression += ", ml_score = :ml_score"
        expression_values[":ml_score"] = fraud_result["ml_score"]

    if "ai_score" in fraud_result:
        update_expression += ", ai_score = :ai_score"
        expression_values[":ai_score"] = fraud_result["ai_score"]

    if "detection_method" in fraud_result:
        update_expression += ", detection_method = :detection_method"
        expression_values[":detection_method"] = fraud_result["detection_method"]

    try:
        table.update_item(
            Key={"event_id": event_id}, UpdateExpression=update_expression, ExpressionAttributeValues=expression_values
        )
    except Exception as e:
        print(f"Error updating event result: {str(e)}")


def get_recent_install_events(
    table_name: str,
    device_id: str,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    attribution_window_sec: int = 3600,
) -> List[Dict[str, Any]]:
    """
    Query install events by device within attribution window

    Args:
        table_name: Name of the DynamoDB table
        device_id: Device ID to query
        start_timestamp: Start timestamp (Unix epoch), defaults to now - attribution_window
        end_timestamp: End timestamp (Unix epoch), defaults to now
        attribution_window_sec: Attribution window in seconds (default: 1 hour)

    Returns:
        List of install event dictionaries
    """
    table = get_table(table_name)

    # Default to attribution window if not specified
    if end_timestamp is None:
        end_timestamp = int(datetime.now(timezone.utc).timestamp())
    if start_timestamp is None:
        start_timestamp = end_timestamp - attribution_window_sec

    try:
        # Query device events
        device_events = query_events_by_device(table_name, device_id, start_timestamp, end_timestamp)

        # Filter for install events only
        install_events = [event for event in device_events if event.get("event_type") == "install"]

        # Sort by timestamp descending (most recent first)
        install_events.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        return install_events
    except Exception as e:
        print(f"Error querying install events: {str(e)}")
        return []


def correlate_click_with_install(
    table_name: str, click_event: Dict[str, Any], attribution_window_sec: int = 3600
) -> Optional[Dict[str, Any]]:
    """
    Find matching install event for a click event within attribution window

    Args:
        table_name: Name of the DynamoDB table
        click_event: Click event dictionary
        attribution_window_sec: Attribution window in seconds (default: 1 hour)

    Returns:
        Matching install event or None if not found
    """
    device_id = click_event.get("device_id")
    click_timestamp = click_event.get("timestamp")

    if not device_id or not click_timestamp:
        return None

    # Look for installs within attribution window after the click
    end_timestamp = click_timestamp + attribution_window_sec

    install_events = get_recent_install_events(
        table_name,
        device_id,
        start_timestamp=click_timestamp,
        end_timestamp=end_timestamp,
        attribution_window_sec=attribution_window_sec,
    )

    if not install_events:
        return None

    # Return the first install (most recent, since sorted descending)
    # But we want the install that occurred after the click
    for install in install_events:
        install_timestamp = install.get("timestamp", 0)
        if install_timestamp >= click_timestamp:
            return install

    return None


def calculate_attribution_window(click_timestamp: int, install_timestamp: int, max_window_sec: int = 3600) -> Optional[int]:
    """
    Calculate if click falls within valid attribution window

    Args:
        click_timestamp: Click event timestamp
        install_timestamp: Install event timestamp
        max_window_sec: Maximum attribution window in seconds (default: 1 hour)

    Returns:
        Time difference in seconds if within window, None otherwise
    """
    if install_timestamp < click_timestamp:
        # Install happened before click - invalid
        return None

    time_diff = install_timestamp - click_timestamp

    if time_diff > max_window_sec:
        # Outside attribution window
        return None

    return time_diff


def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Convert float values to Decimal for DynamoDB compatibility

    Args:
        obj: Object to convert

    Returns:
        Object with floats converted to Decimal
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj
