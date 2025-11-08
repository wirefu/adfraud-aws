"""
Fraud Orchestrator Lambda Function
Routes events to ML or ML+AI analysis path based on ML score
"""

import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3

# Import feature extraction
try:
    from feature_extractor import extract_features
except ImportError:
    # Fallback for Lambda deployment
    sys.path.append(os.path.dirname(__file__))
    from feature_extractor import extract_features

# Initialize AWS clients
sagemaker = boto3.client("sagemaker-runtime")
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")

# Environment variables
SAGEMAKER_ENDPOINT = os.environ.get("SAGEMAKER_ENDPOINT", "fraudguard-xgboost-endpoint")
AI_ANALYZER_FUNCTION = os.environ.get("AI_ANALYZER_FUNCTION", "fraudguard-ai-analyzer")
DECISION_COMBINER_FUNCTION = os.environ.get("DECISION_COMBINER_FUNCTION", "")  # Optional: use dedicated combiner
TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")

# Decision thresholds
FRAUD_THRESHOLD = 0.8  # Block immediately if ML score > 0.8
LEGITIMATE_THRESHOLD = 0.3  # Allow immediately if ML score < 0.3
BORDERLINE_MIN = 0.3  # Route to AI if score between 0.3 and 0.8
BORDERLINE_MAX = 0.8

# In-memory cache for fraud rate lookups (5 minute TTL)
_fraud_rate_cache = {}
CACHE_TTL = 300  # 5 minutes in seconds


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Orchestrate fraud detection workflow

    Args:
        event: Event from ingestion handler or API Gateway
        context: Lambda context object

    Returns:
        Fraud detection result
    """
    start_time = datetime.now(timezone.utc)

    try:
        # Extract event data
        if "body" in event:
            body = json.loads(event.get("body", "{}"))
        else:
            body = event

        event_id = body.get("event_id")
        if not event_id:
            return create_error_response(400, "Missing event_id")

        # Get context data from DynamoDB
        # Check if this is a Google Ads event (limited signals)
        is_google_ads = body.get('source') == 'google_ads'
        
        if is_google_ads:
            context_data = get_google_ads_context_data(
                body.get('keyword'),
                body.get('target_id'),
                body.get('gclid')
            )
        else:
            context_data = get_context_data(
                event_id,
                body.get('device_id'),
                body.get('ip_address')
            )
        # Extract features for ML model
        feature_vector = extract_features(body, context_data)

        # Call SageMaker endpoint for ML score
        ml_score = get_ml_score(feature_vector)

        # Decision logic
        if ml_score > FRAUD_THRESHOLD:
            # Clear fraud - block immediately
            result = create_ml_only_response(event_id, ml_score, True, "block", start_time)
        elif ml_score < LEGITIMATE_THRESHOLD:
            # Clear legitimate - allow immediately
            result = create_ml_only_response(event_id, ml_score, False, "allow", start_time)
        else:
            # Borderline case - route to AI analysis
            result = route_to_ai_analysis(body, ml_score, feature_vector, start_time)

        # Store result in DynamoDB
        store_result(event_id, result)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(result),
        }

    except Exception as e:
        return create_error_response(500, f"Orchestration error: {str(e)}")


def get_cached_fraud_rate(cache_key: str, fetch_func) -> float:
    """
    Get cached fraud rate or fetch and cache if expired
    
    Args:
        cache_key: Cache key (e.g., 'keyword:buy-shoes' or 'target:placement-123')
        fetch_func: Function to call if cache miss or expired
        
    Returns:
        Fraud rate (0.0-1.0)
    """
    now = time.time()
    
    # Check cache
    if cache_key in _fraud_rate_cache:
        value, timestamp = _fraud_rate_cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return value
    
    # Cache miss or expired - fetch and cache
    value = fetch_func()
    _fraud_rate_cache[cache_key] = (value, now)
    return value


def get_google_ads_context_data(keyword: str, target_id: str, gclid: str) -> Dict[str, Any]:
    """
    Get context data for Google Ads events (limited signals)
    
    Args:
        keyword: Keyword from Google Ads
        target_id: Target/placement ID
        gclid: Google Click ID
        
    Returns:
        Context data dictionary with Google-specific features
    """
    if not TABLE_NAME:
        return {}
    
    try:
        # Import storage utilities
        try:
            from storage.dynamodb_utils import (
                get_keyword_fraud_rate,
                get_target_fraud_rate
            )
        except ImportError:
            # Fallback - define simple functions
            def get_keyword_fraud_rate(table_name, keyword, days=30):
                return 0.0
            def get_target_fraud_rate(table_name, target_id, days=30):
                return 0.0
        
        # Get historical fraud rates with caching
        keyword_fraud_rate = 0.0
        if keyword:
            cache_key = f'keyword:{keyword}'
            keyword_fraud_rate = get_cached_fraud_rate(
                cache_key,
                lambda: get_keyword_fraud_rate(TABLE_NAME, keyword, days=30)
            )
        
        target_fraud_rate = 0.0
        if target_id:
            cache_key = f'target:{target_id}'
            target_fraud_rate = get_cached_fraud_rate(
                cache_key,
                lambda: get_target_fraud_rate(TABLE_NAME, target_id, days=30)
            )
        
        # Analyze GCLID pattern (simplified - would use more sophisticated analysis)
        gclid_pattern_score = analyze_gclid_pattern(gclid) if gclid else 0.5
        
        return {
            'keyword_fraud_rate': keyword_fraud_rate,
            'target_fraud_rate': target_fraud_rate,
            'gclid_pattern_score': gclid_pattern_score,
            # Set missing signals to defaults
            'ip_click_count_24h': 0,
            'device_click_count_1h': 0,
            'time_since_last_click': None
        }
    except Exception as e:
        print(f"Error getting Google Ads context data: {str(e)}")
        return {}


def analyze_gclid_pattern(gclid: str) -> float:
    """
    Analyze GCLID for bot-like patterns
    
    Args:
        gclid: Google Click ID
        
    Returns:
        Pattern score (0.0-1.0, higher = more suspicious)
    """
    if not gclid:
        return 0.5
    
    # Simple pattern analysis
    # In production, would use more sophisticated analysis
    # Check for suspicious patterns like:
    # - Low entropy (repetitive characters)
    # - Sequential patterns
    # - Unusual character distributions
    
    from feature_extractor import calculate_entropy
    
    entropy = calculate_entropy(gclid)
    
    # Lower entropy = more suspicious (bot-like patterns)
    # Normalize to 0-1 (inverse: low entropy = high suspicion)
    pattern_score = 1.0 - entropy
    
    return pattern_score


def get_context_data(event_id: str, device_id: str, ip_address: str) -> Dict[str, Any]:
    """
    Get context data from DynamoDB for feature enrichment

    Args:
        event_id: Event ID
        device_id: Device ID
        ip_address: IP address

    Returns:
        Context data dictionary
    """
    if not TABLE_NAME:
        return {}

    try:
        # Import storage utilities
        try:
            from storage.dynamodb_utils import (
                get_device_click_count_1h,
                get_time_since_last_click,
                query_events_by_device,
                get_recent_install_events,
                correlate_click_with_install,
                calculate_attribution_window,
            )
        except ImportError:
            # Fallback - define simple query function
            def query_events_by_device(table_name, device_id, start_ts, end_ts):
                table = dynamodb.Table(table_name)
                try:
                    response = table.query(
                        IndexName="device-timestamp-index",
                        KeyConditionExpression="device_id = :device_id AND timestamp BETWEEN :start AND :end",
                        ExpressionAttributeValues={":device_id": device_id, ":start": start_ts, ":end": end_ts},
                    )
                    return response.get("Items", [])
                except:
                    return []

            def get_time_since_last_click(table_name, device_id):
                # Simplified implementation
                return None

            def get_recent_install_events(table_name, device_id, start_ts=None, end_ts=None, attribution_window_sec=3600):
                return []

            def correlate_click_with_install(table_name, click_event, attribution_window_sec=3600):
                return None

            def calculate_attribution_window(click_timestamp, install_timestamp, max_window_sec=3600):
                return None

        # Get device history
        now = datetime.now(timezone.utc)
        one_hour_ago = int((now - timedelta(hours=1)).timestamp())
        now_timestamp = int(now.timestamp())

        device_events = query_events_by_device(TABLE_NAME, device_id, one_hour_ago, now_timestamp)
        device_click_count_1h = len(device_events)

        # Get time since last click
        time_since_last_click = get_time_since_last_click(TABLE_NAME, device_id)

        # Get IP click count (simplified - would need GSI in production)
        # For now, use placeholder
        ip_click_count_24h = 0

        # Get install event correlation for click injection detection
        click_injection_data = get_click_injection_data(event_id, device_id, ip_address)

        # Get conversion data for incentivized click detection
        conversion_data = get_conversion_data(device_id, ip_address)

        # Get competitor IPs for competitor clicking detection
        competitor_data = get_competitor_data(ip_address)

        return {
            "ip_click_count_24h": ip_click_count_24h,
            "device_click_count_1h": device_click_count_1h,
            "time_since_last_click": time_since_last_click,
            **click_injection_data,
            **conversion_data,
            **competitor_data,
        }
    except Exception as e:
        print(f"Error getting context data: {str(e)}")
        return {}


def get_ml_score(feature_vector: List[float]) -> float:
    """
    Get ML fraud score from SageMaker endpoint

    Args:
        feature_vector: List of feature values in CSV format

    Returns:
        ML fraud score (0.0-1.0)
    """
    if not SAGEMAKER_ENDPOINT:
        # Fallback: return placeholder score for development
        print("Warning: SAGEMAKER_ENDPOINT not set, using fallback score")
        return 0.5

    try:
        # Convert feature vector to CSV format (SageMaker XGBoost expects CSV)
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(feature_vector)
        csv_data = csv_buffer.getvalue()

        # Invoke SageMaker endpoint
        response = sagemaker.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT, ContentType="text/csv", Body=csv_data.encode("utf-8")
        )

        # Parse response (XGBoost returns predictions as CSV)
        result = response["Body"].read().decode("utf-8")
        prediction = float(result.strip())

        # XGBoost returns probability, which is already 0-1
        return prediction

    except Exception as e:
        # Fallback on error
        print(f"Error calling SageMaker endpoint: {str(e)}")
        import traceback

        traceback.print_exc()
        return 0.5


def route_to_ai_analysis(
    body: Dict[str, Any], ml_score: float, feature_vector: List[float], start_time: datetime
) -> Dict[str, Any]:
    """
    Route borderline cases to AI analysis

    Args:
        body: Original event body
        ml_score: ML fraud score
        features: Extracted features
        start_time: Request start time

    Returns:
        Combined ML+AI result
    """
    try:
        # Invoke AI analyzer Lambda
        ai_response = lambda_client.invoke(
            FunctionName=AI_ANALYZER_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps({"body": json.dumps({**body, "ml_score": ml_score, "feature_vector": feature_vector})}),
        )

        ai_result = json.loads(ai_response["Payload"].read())
        ai_data = json.loads(ai_result.get("body", "{}"))

        # Use dedicated decision combiner if available, otherwise combine inline
        if DECISION_COMBINER_FUNCTION:
            return use_decision_combiner_lambda(body, ml_score, ai_data, start_time)
        else:
            return combine_scores_inline(body, ml_score, ai_data, start_time)

    except Exception as e:
        # Fallback to ML-only result if AI analysis fails
        print(f"Error in AI analysis: {str(e)}")
        import traceback

        traceback.print_exc()
        return create_ml_only_response(body.get("event_id"), ml_score, ml_score > 0.65, "review", start_time)


def use_decision_combiner_lambda(
    body: Dict[str, Any], ml_score: float, ai_data: Dict[str, Any], start_time: datetime
) -> Dict[str, Any]:
    """
    Use dedicated decision combiner Lambda function

    Args:
        body: Original event body
        ml_score: ML fraud score
        ai_data: AI analysis result
        start_time: Request start time

    Returns:
        Combined result from decision combiner
    """
    try:
        # Invoke decision combiner Lambda
        combiner_response = lambda_client.invoke(
            FunctionName=DECISION_COMBINER_FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps(
                {"body": json.dumps({"event_id": body.get("event_id"), "ml_score": ml_score, "ai_result": ai_data})}
            ),
        )

        combiner_result = json.loads(combiner_response["Payload"].read())
        result = json.loads(combiner_result.get("body", "{}"))

        # Add latency
        latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        result["latency_ms"] = latency_ms

        return result

    except Exception as e:
        # Fallback to inline combination
        print(f"Error calling decision combiner: {str(e)}")
        return combine_scores_inline(body, ml_score, ai_data, start_time)


def combine_scores_inline(
    body: Dict[str, Any], ml_score: float, ai_data: Dict[str, Any], start_time: datetime
) -> Dict[str, Any]:
    """
    Combine ML and AI scores inline (fallback method)

    Args:
        body: Original event body
        ml_score: ML fraud score
        ai_data: AI analysis result
        start_time: Request start time

    Returns:
        Combined result
    """
    # Combine ML and AI scores
    ai_score = ai_data.get("ai_score", ml_score)
    ai_confidence = ai_data.get("confidence", 0.5)

    # Ensemble scoring: 40% ML, 60% AI (when AI confidence > 0.8)
    if ai_confidence > 0.8:
        final_score = (ml_score * 0.4) + (ai_score * 0.6)
    else:
        final_score = (ml_score * 0.6) + (ai_score * 0.4)

    # Final decision
    is_fraud = final_score > 0.65
    action = "block" if is_fraud else ("review" if final_score > 0.5 else "allow")

    latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "event_id": body.get("event_id"),
        "is_fraud": is_fraud,
        "fraud_score": final_score,
        "ml_score": ml_score,
        "ai_score": ai_score,
        "confidence": ai_confidence,
        "detection_method": "ml_ai_ensemble",
        "fraud_signals": ai_data.get("fraud_signals", []),
        "reasoning": ai_data.get("reasoning", ""),
        "recommended_action": action,
        "latency_ms": latency_ms,
    }


def create_ml_only_response(
    event_id: str, ml_score: float, is_fraud: bool, action: str, start_time: datetime
) -> Dict[str, Any]:
    """
    Create ML-only response

    Args:
        event_id: Event ID
        ml_score: ML fraud score
        is_fraud: Fraud verdict
        action: Recommended action
        start_time: Request start time

    Returns:
        ML-only response dictionary
    """
    latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "event_id": event_id,
        "is_fraud": is_fraud,
        "fraud_score": ml_score,
        "confidence": 0.8 if ml_score > FRAUD_THRESHOLD or ml_score < LEGITIMATE_THRESHOLD else 0.5,
        "detection_method": "ml_only",
        "latency_ms": latency_ms,
        "action": action,
    }


def store_result(event_id: str, result: Dict[str, Any]) -> None:
    """
    Store fraud detection result in DynamoDB

    Args:
        event_id: Event ID
        result: Detection result
    """
    if not TABLE_NAME:
        return

    try:
        # Import storage utilities
        try:
            import sys
            import os
            # Add parent directory to path for Lambda deployment
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from storage.dynamodb_utils import update_event_result
            # Use storage utility function (preferred)
            update_event_result(TABLE_NAME, event_id, result)
            return
        except ImportError:
            # Fallback: use direct DynamoDB update
            pass
        
        # Fallback: use direct DynamoDB update
        from decimal import Decimal
        
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
        
        # Convert entire result to Decimal first
        result = convert_floats_to_decimal(result)
        
        table = dynamodb.Table(TABLE_NAME)
        update_expression = "SET fraud_result = :result, updated_at = :timestamp"
        expression_values = {":result": result, ":timestamp": datetime.now(timezone.utc).isoformat()}
        
        # Add top-level fields for dashboard compatibility
        if "is_fraud" in result:
            update_expression += ", is_fraud = :is_fraud"
            expression_values[":is_fraud"] = result["is_fraud"]
        
        if "fraud_score" in result:
            update_expression += ", fraud_score = :fraud_score"
            expression_values[":fraud_score"] = result["fraud_score"]  # Already converted to Decimal
        
        if "ml_score" in result:
            update_expression += ", ml_score = :ml_score"
            expression_values[":ml_score"] = result["ml_score"]  # Already converted to Decimal
        
        if "ai_score" in result:
            update_expression += ", ai_score = :ai_score"
            expression_values[":ai_score"] = result["ai_score"]  # Already converted to Decimal
        
        if "primary_fraud_type" in result:
            update_expression += ", primary_fraud_type = :primary_fraud_type"
            expression_values[":primary_fraud_type"] = result["primary_fraud_type"]
        
        if "fraud_signals" in result:
            update_expression += ", fraud_signals = :fraud_signals"
            expression_values[":fraud_signals"] = result["fraud_signals"]
        
        if "reasoning" in result:
            update_expression += ", reasoning = :reasoning"
            expression_values[":reasoning"] = result["reasoning"]
        
        table.update_item(
            Key={"event_id": event_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )
        
    except Exception as e:
        print(f"Error storing result: {str(e)}")
        import traceback
        traceback.print_exc()


def get_click_injection_data(event_id: str, device_id: str, ip_address: str) -> Dict[str, Any]:
    """
    Get click injection detection data by correlating clicks with installs

    Args:
        event_id: Event ID
        device_id: Device ID
        ip_address: IP address

    Returns:
        Dictionary with click injection detection features
    """
    if not TABLE_NAME or not device_id:
        return {
            "click_to_install_time_sec": 0.0,
            "has_recent_install": False,
            "install_broadcast_detected": False,
            "click_injection_risk_score": 0.0,
        }

    try:
        # Import storage utilities
        try:
            from storage.dynamodb_utils import (
                get_event,
                get_recent_install_events,
                correlate_click_with_install,
                calculate_attribution_window,
            )
        except ImportError:
            return {
                "click_to_install_time_sec": 0.0,
                "has_recent_install": False,
                "install_broadcast_detected": False,
                "click_injection_risk_score": 0.0,
            }

        # Get current event
        current_event = get_event(TABLE_NAME, event_id)
        if not current_event:
            return {
                "click_to_install_time_sec": 0.0,
                "has_recent_install": False,
                "install_broadcast_detected": False,
                "click_injection_risk_score": 0.0,
            }

        event_type = current_event.get("event_type")
        event_timestamp = current_event.get("timestamp")

        # Only process click events for click injection detection
        if event_type != "click":
            return {
                "click_to_install_time_sec": 0.0,
                "has_recent_install": False,
                "install_broadcast_detected": False,
                "click_injection_risk_score": 0.0,
            }

        # Correlate click with install
        install_event = correlate_click_with_install(TABLE_NAME, current_event, attribution_window_sec=3600)

        if not install_event:
            return {
                "click_to_install_time_sec": 0.0,
                "has_recent_install": False,
                "install_broadcast_detected": False,
                "click_injection_risk_score": 0.0,
            }

        install_timestamp = install_event.get("timestamp", 0)
        click_to_install_time = calculate_attribution_window(event_timestamp, install_timestamp, max_window_sec=3600)

        if click_to_install_time is None:
            return {
                "click_to_install_time_sec": 0.0,
                "has_recent_install": False,
                "install_broadcast_detected": False,
                "click_injection_risk_score": 0.0,
            }

        # Calculate click injection risk score
        # <1 second is highly suspicious (likely click injection)
        # 1-10 seconds is suspicious
        # 30-300 seconds is normal
        has_recent_install = click_to_install_time > 0
        install_broadcast_detected = click_to_install_time < 1.0  # <1 second suggests install broadcast monitoring

        # Risk score: inverse of time (shorter time = higher risk)
        # Normalize to 0-1 range
        if click_to_install_time < 1.0:
            risk_score = 0.95  # Highly suspicious
        elif click_to_install_time < 10.0:
            risk_score = 0.7  # Suspicious
        elif click_to_install_time < 30.0:
            risk_score = 0.4  # Somewhat suspicious
        else:
            risk_score = max(0.0, 1.0 - (click_to_install_time / 300.0))  # Normal range

        return {
            "click_to_install_time_sec": float(click_to_install_time),
            "has_recent_install": has_recent_install,
            "install_broadcast_detected": install_broadcast_detected,
            "click_injection_risk_score": risk_score,
        }

    except Exception as e:
        print(f"Error getting click injection data: {str(e)}")
        return {
            "click_to_install_time_sec": 0.0,
            "has_recent_install": False,
            "install_broadcast_detected": False,
            "click_injection_risk_score": 0.0,
        }


def get_conversion_data(device_id: str, ip_address: str) -> Dict[str, Any]:
    """
    Get conversion data for incentivized click detection

    Args:
        device_id: Device ID
        ip_address: IP address

    Returns:
        Dictionary with conversion metrics
    """
    if not TABLE_NAME:
        return {"clicks_count": 0, "conversions_count": 0, "conversion_rate": 0.0}

    try:
        # Import storage utilities
        try:
            from storage.dynamodb_utils import query_events_by_device
        except ImportError:
            return {"clicks_count": 0, "conversions_count": 0, "conversion_rate": 0.0}

        # Get device events in last 24 hours
        now = datetime.now(timezone.utc)
        one_day_ago = int((now - timedelta(days=1)).timestamp())
        now_timestamp = int(now.timestamp())

        device_events = query_events_by_device(TABLE_NAME, device_id, one_day_ago, now_timestamp)

        # Count clicks and conversions
        clicks_count = sum(1 for e in device_events if e.get("event_type") == "click")
        conversions_count = sum(1 for e in device_events if e.get("event_type") in ["install", "conversion"])

        # Calculate conversion rate
        conversion_rate = float(conversions_count) / float(clicks_count) if clicks_count > 0 else 0.0

        return {"clicks_count": clicks_count, "conversions_count": conversions_count, "conversion_rate": conversion_rate}

    except Exception as e:
        print(f"Error getting conversion data: {str(e)}")
        return {"clicks_count": 0, "conversions_count": 0, "conversion_rate": 0.0}


def get_competitor_data(ip_address: str) -> Dict[str, Any]:
    """
    Get competitor detection data

    Args:
        ip_address: IP address

    Returns:
        Dictionary with competitor detection data
    """
    # In production, load competitor IPs from configuration or database
    # For now, use environment variable or default empty list
    competitor_ips = os.environ.get("COMPETITOR_IPS", "").split(",") if os.environ.get("COMPETITOR_IPS") else []

    # Filter out empty strings
    competitor_ips = [ip.strip() for ip in competitor_ips if ip.strip()]

    try:
        from feature_extractor import is_competitor_ip, is_business_ip

        ip_is_competitor = is_competitor_ip(ip_address, competitor_ips)
        ip_is_business = is_business_ip(ip_address)

        return {"competitor_ips": competitor_ips, "ip_is_competitor": ip_is_competitor, "ip_is_business": ip_is_business}

    except Exception as e:
        print(f"Error getting competitor data: {str(e)}")
        return {"competitor_ips": [], "ip_is_competitor": False, "ip_is_business": False}


def calculate_click_injection_risk(click_to_install_time: float) -> float:
    """
    Calculate click injection risk score based on timing

    Args:
        click_to_install_time: Time between click and install in seconds

    Returns:
        Risk score (0.0-1.0)
    """
    if click_to_install_time <= 0:
        return 0.0

    # <1 second is highly suspicious (likely click injection)
    if click_to_install_time < 1.0:
        return 0.95

    # 1-10 seconds is suspicious
    if click_to_install_time < 10.0:
        return 0.7

    # 10-30 seconds is somewhat suspicious
    if click_to_install_time < 30.0:
        return 0.4

    # 30-300 seconds is normal range
    # Risk decreases as time increases
    return max(0.0, 1.0 - (click_to_install_time / 300.0))


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create standardized error response

    Args:
        status_code: HTTP status code
        message: Error message

    Returns:
        API Gateway error response
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"error": message, "status": "error"}),
    }
