#!/usr/bin/env python3
"""
Import Historical Google Ads Data
Fetches data from Nov 2023 to Nov 2024, shifts dates forward by 1 year, and stores in DynamoDB
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import random

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dashboard.google_ads_api_integration import (
    get_google_ads_api_client,
    fetch_google_ads_performance,
    fetch_google_ads_keywords,
    fetch_google_ads_placements,
    fetch_google_ads_click_details,
    is_within_90_days
)
from src.storage.dynamodb_utils import store_event, convert_floats_to_decimal

# Configuration
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'fraudguard-events-dev')
YEAR_OFFSET = 1  # Shift dates forward by 1 year


def shift_date_forward(date_str: str, year_offset: int = 1) -> datetime:
    """
    Shift a date string forward by the specified number of years
    Handles leap year edge cases (e.g., Feb 29 -> Feb 28 in non-leap years)
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        year_offset: Number of years to add (default: 1)
    
    Returns:
        datetime object with shifted date
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    new_year = date_obj.year + year_offset
    
    # Handle leap year edge case: if original date is Feb 29 and new year is not a leap year
    if date_obj.month == 2 and date_obj.day == 29:
        # Check if new year is a leap year
        is_leap = (new_year % 4 == 0 and new_year % 100 != 0) or (new_year % 400 == 0)
        if not is_leap:
            # Shift to Feb 28 in non-leap year
            return date_obj.replace(year=new_year, day=28)
    
    try:
        return date_obj.replace(year=new_year)
    except ValueError:
        # Fallback: if date is invalid (e.g., Feb 29 -> non-leap year), use last day of month
        from calendar import monthrange
        last_day = monthrange(new_year, date_obj.month)[1]
        return date_obj.replace(year=new_year, day=min(date_obj.day, last_day))


def convert_click_details_to_events(
    click_details: List[Dict[str, Any]],
    year_offset: int = 1
) -> List[Dict[str, Any]]:
    """
    Convert ClickView click details directly to events (no aggregation needed)
    These already have real GCLIDs and individual click data
    
    Args:
        click_details: Click detail data from ClickView resource
        year_offset: Number of years to shift dates forward
    
    Returns:
        List of events ready for DynamoDB storage
    """
    events = []
    
    for click in click_details:
        date_str = click.get('date', '')
        if not date_str:
            continue
        
        # Shift date forward
        shifted_date = shift_date_forward(date_str, year_offset)
        
        # Use the timestamp from click details, but shift the date
        original_timestamp = click.get('timestamp', 0)
        if original_timestamp:
            # Adjust timestamp by year offset
            original_dt = datetime.fromtimestamp(original_timestamp, tz=timezone.utc)
            shifted_dt = original_dt.replace(year=original_dt.year + year_offset)
            event_timestamp = int(shifted_dt.timestamp())
        else:
            # Fallback: use shifted date at the hour specified
            hour = click.get('hour', 12)
            event_timestamp = int(shifted_date.replace(hour=hour, minute=0, second=0).timestamp())
        
        # Create event with real GCLID and all click details
        event = {
            'event_id': f'google-ads-clickview-{click.get("gclid", "")}-{event_timestamp}-{uuid.uuid4().hex[:8]}',
            'timestamp': event_timestamp,
            'event_type': 'click',
            'source': 'google_ads_api',
            'campaign_id': click.get('campaign_id', ''),
            'campaign_name': click.get('campaign_name', ''),
            'gclid': click.get('gclid', ''),  # REAL GCLID from ClickView!
            'keyword': click.get('keyword', ''),
            'target_id': '',  # Not available in ClickView
            'ad_group_id': click.get('ad_group_id', ''),
            'ad_group_name': click.get('ad_group_name', ''),
            'match_type': click.get('match_type', ''),
            'cost_micros': 0,  # Not available in ClickView
            'clicks': 1,
            'impressions': 0,  # Not available in ClickView
            'conversions': 0,  # Not available in ClickView
            'ctr': 0.0,
            'is_fraud': False,
            'fraud_score': 0.0,
            'primary_fraud_type': 'legitimate',
            'fraud_signals': [],
            'original_date': date_str,
            'shifted_date': shifted_date.strftime('%Y-%m-%d'),
            'data_source': 'clickview',  # Mark as ClickView data
            'city_interest': click.get('city_interest', ''),
            'country_interest': click.get('country_interest', ''),
            'metro_interest': click.get('metro_interest', ''),
            'city_location': click.get('city_location', ''),
            'country_location': click.get('country_location', ''),
            'metro_location': click.get('metro_location', ''),
            'page_number': click.get('page_number', 0),
            'slot': click.get('slot', ''),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        events.append(event)
    
    return events


def convert_performance_to_events(
    performance_data: List[Dict[str, Any]],
    keyword_data: List[Dict[str, Any]],
    placement_data: List[Dict[str, Any]],
    year_offset: int = 1
) -> List[Dict[str, Any]]:
    """
    Convert Google Ads API performance data into event format for storage
    
    Args:
        performance_data: Campaign performance data from API
        keyword_data: Keyword performance data from API
        placement_data: Placement performance data from API
        year_offset: Number of years to shift dates forward
    
    Returns:
        List of events ready for DynamoDB storage
    """
    events = []
    
    # Build keyword lookup by (campaign_id, date)
    keyword_lookup = {}
    for kw in keyword_data:
        key = (str(kw.get('campaign_id', '')), kw.get('date', ''))
        if key not in keyword_lookup:
            keyword_lookup[key] = []
        keyword_lookup[key].append(kw)
    
    # Build placement lookup by (campaign_id, date)
    placement_lookup = {}
    for pl in placement_data:
        key = (str(pl.get('campaign_id', '')), pl.get('date', ''))
        if key not in placement_lookup:
            placement_lookup[key] = []
        placement_lookup[key].append(pl)
    
    # Process performance data (campaign-level)
    for perf in performance_data:
        campaign_id = str(perf.get('campaign_id', ''))
        clicks = perf.get('clicks', 0)
        cost_micros = perf.get('cost_micros', 0)
        avg_cpc_micros = perf.get('avg_cpc_micros', 0)
        date_str = perf.get('date', '')
        original_date = date_str
        
        if not date_str:
            continue
        
        # Shift date forward
        shifted_date = shift_date_forward(date_str, year_offset)
        
        # Get matching keywords and placements for this date
        matching_keywords = keyword_lookup.get((campaign_id, original_date), [])
        matching_placements = placement_lookup.get((campaign_id, original_date), [])
        
        # Create individual click events from aggregated data
        total_impressions = perf.get('impressions', 0)
        total_conversions = perf.get('conversions', 0)
        
        for i in range(clicks):
            # Distribute timestamp within the day (spread across 24 hours)
            click_offset = random.uniform(0, 1)  # Random time within day (0.0 to 1.0)
            event_timestamp = int((shifted_date + timedelta(seconds=int(click_offset * 86400))).timestamp())
            
            # Generate a unique GCLID for this event
            gclid = f"API-{campaign_id}-{event_timestamp}-{i}-{uuid.uuid4().hex[:8]}"
            
            # Calculate per-click metrics
            impressions_per_click = total_impressions / clicks if clicks > 0 else 0
            has_conversion = random.random() < (total_conversions / clicks) if clicks > 0 else False
            click_cost_micros = avg_cpc_micros if avg_cpc_micros > 0 else (cost_micros / clicks if clicks > 0 else 0)
            
            # Assign keyword and placement if available
            keyword = ''
            ad_group_id = ''
            target_id = ''
            
            if matching_keywords:
                kw = random.choice(matching_keywords)
                keyword = kw.get('keyword', '')
                ad_group_id = str(kw.get('ad_group_id', ''))
            
            if matching_placements:
                pl = random.choice(matching_placements)
                target_id = str(pl.get('placement_id', ''))
                if not ad_group_id:
                    ad_group_id = str(pl.get('ad_group_id', ''))
            
            # Create event in DynamoDB format
            event = {
                'event_id': f'google-ads-historical-{campaign_id}-{event_timestamp}-{i}-{uuid.uuid4().hex[:8]}',
                'timestamp': event_timestamp,
                'event_type': 'click',
                'source': 'google_ads_api',
                'campaign_id': campaign_id,
                'campaign_name': perf.get('campaign_name', ''),
                'gclid': gclid,
                'keyword': keyword,
                'target_id': target_id,
                'ad_group_id': ad_group_id,
                'cost_micros': int(click_cost_micros),
                'clicks': 1,
                'impressions': int(impressions_per_click),
                'conversions': 1 if has_conversion else 0,
                'ctr': float(perf.get('ctr', 0.0)),
                'is_fraud': False,  # Default to legitimate, can be updated by fraud detection
                'fraud_score': 0.0,
                'primary_fraud_type': 'legitimate',
                'fraud_signals': [],
                'original_date': original_date,  # Keep original date for reference
                'shifted_date': shifted_date.strftime('%Y-%m-%d'),
                'data_source': 'aggregated',  # Mark as aggregated data (synthetic GCLIDs)
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            events.append(event)
    
    return events


def import_historical_data(
    table_name: str,
    start_date: str = "2023-11-01",
    end_date: str = "2024-11-30",
    year_offset: int = 1,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Import historical Google Ads data from API and store in DynamoDB
    
    Args:
        table_name: DynamoDB table name
        start_date: Start date in YYYY-MM-DD format (default: 2023-11-01)
        end_date: End date in YYYY-MM-DD format (default: 2024-11-30)
        year_offset: Number of years to shift dates forward (default: 1)
        batch_size: Number of events to process before printing progress
    
    Returns:
        Dictionary with import statistics
    """
    print(f"🚀 Starting historical Google Ads data import...")
    print(f"   Date range: {start_date} to {end_date}")
    print(f"   Year offset: +{year_offset} years")
    print(f"   Table: {table_name}")
    print()
    
    # Check if API client is available
    client = get_google_ads_api_client()
    if not client:
        print("❌ Error: Google Ads API client not available")
        print("   Please configure Google Ads API credentials")
        return {
            'success': False,
            'error': 'Google Ads API client not available',
            'events_imported': 0
        }
    
    print("✅ Google Ads API client initialized")
    print()
    
    try:
        # Fetch all performance data (use historical_data=True to get Nov 2023 - Nov 2024)
        print("📊 Fetching campaign performance data...")
        performance_data = fetch_google_ads_performance(
            campaign_id=None,  # Get all campaigns
            days=395,  # Nov 2023 to Nov 2024 is ~395 days
            hours=None,
            use_historical_data=True,
            year_offset=year_offset
        )
        print(f"   ✅ Fetched {len(performance_data)} performance records")
        
        print("📊 Fetching keyword performance data...")
        keyword_data = fetch_google_ads_keywords(
            campaign_id=None,
            days=395,
            hours=None,
            use_historical_data=True,
            year_offset=year_offset
        )
        print(f"   ✅ Fetched {len(keyword_data)} keyword records")
        
        print("📊 Fetching placement performance data...")
        try:
            placement_data = fetch_google_ads_placements(
                campaign_id=None,
                days=395,
                hours=None,
                use_historical_data=True,
                year_offset=year_offset
            )
            print(f"   ✅ Fetched {len(placement_data)} placement records")
        except Exception as e:
            print(f"   ⚠️  Warning: Could not fetch placement data: {str(e)}")
            print(f"   Continuing without placement data...")
            placement_data = []
        print()
        
        # Convert to events using hybrid approach
        print("🔄 Converting API data to events (hybrid approach)...")
        print("   📊 Using ClickView for recent dates (last 90 days) with real GCLIDs")
        print("   📊 Using aggregated data for older dates (beyond 90 days)")
        print()
        
        # Separate dates into recent (ClickView) and historical (aggregated)
        # Note: Check original_date if available, otherwise use date
        recent_dates = set()
        historical_performance = []
        historical_keywords = []
        historical_placements = []
        
        for perf in performance_data:
            # Use original_date if available (before year shift), otherwise use date
            date_str = perf.get('original_date') or perf.get('date', '')
            if date_str:
                # Check if original date (before shifting) is within 90 days
                # We check the original date because ClickView works on actual dates, not shifted ones
                if is_within_90_days(date_str):
                    recent_dates.add(date_str)
                else:
                    historical_performance.append(perf)
            else:
                historical_performance.append(perf)
        
        # Filter keyword and placement data
        for kw in keyword_data:
            date_str = kw.get('date', '')
            if date_str and date_str not in recent_dates:
                historical_keywords.append(kw)
        
        for pl in placement_data:
            date_str = pl.get('date', '')
            if date_str and date_str not in recent_dates:
                historical_placements.append(pl)
        
        events = []
        
        # Process recent dates with ClickView (real GCLIDs)
        if recent_dates:
            print(f"   🔍 Fetching ClickView data for {len(recent_dates)} recent dates...")
            clickview_events = []
            for date_str in sorted(recent_dates):
                try:
                    click_details = fetch_google_ads_click_details(date=date_str)
                    if click_details:
                        date_events = convert_click_details_to_events(click_details, year_offset=year_offset)
                        clickview_events.extend(date_events)
                        print(f"      ✅ {date_str}: {len(date_events)} clicks with real GCLIDs")
                except Exception as e:
                    print(f"      ⚠️  {date_str}: Error fetching ClickView - {str(e)}")
                    # Fall back to aggregated for this date
                    date_perf = [p for p in performance_data if p.get('date') == date_str]
                    date_kw = [k for k in keyword_data if k.get('date') == date_str]
                    date_pl = [p for p in placement_data if p.get('date') == date_str]
                    historical_performance.extend(date_perf)
                    historical_keywords.extend(date_kw)
                    historical_placements.extend(date_pl)
            
            events.extend(clickview_events)
            print(f"   ✅ Created {len(clickview_events)} events from ClickView (real GCLIDs)")
            print()
        
        # Process historical dates with aggregated data (synthetic GCLIDs)
        if historical_performance:
            print(f"   📊 Processing {len(historical_performance)} historical performance records...")
            aggregated_events = convert_performance_to_events(
                historical_performance,
                historical_keywords,
                historical_placements,
                year_offset=year_offset
            )
            events.extend(aggregated_events)
            print(f"   ✅ Created {len(aggregated_events)} events from aggregated data (synthetic GCLIDs)")
            print()
        
        print(f"   📊 Total events created: {len(events)}")
        print(f"      - ClickView (real GCLIDs): {len([e for e in events if e.get('data_source') == 'clickview'])}")
        print(f"      - Aggregated (synthetic GCLIDs): {len([e for e in events if e.get('data_source') == 'aggregated'])}")
        print()
        
        # Store events in DynamoDB
        print(f"💾 Storing events in DynamoDB (batch size: {batch_size})...")
        stored_count = 0
        error_count = 0
        
        for i, event in enumerate(events):
            try:
                # Convert floats to Decimal for DynamoDB
                event = convert_floats_to_decimal(event)
                
                # Store event
                store_event(table_name, event)
                stored_count += 1
                
                # Print progress
                if (i + 1) % batch_size == 0:
                    print(f"   📦 Stored {i + 1}/{len(events)} events ({stored_count} successful, {error_count} errors)")
            
            except Exception as e:
                error_count += 1
                print(f"   ⚠️  Error storing event {i + 1}: {str(e)}")
                if error_count > 10:
                    print(f"   ❌ Too many errors, stopping import")
                    break
        
        print()
        print("✅ Import complete!")
        print(f"   📊 Total events: {len(events)}")
        print(f"   ✅ Successfully stored: {stored_count}")
        print(f"   ❌ Errors: {error_count}")
        
        return {
            'success': True,
            'events_imported': stored_count,
            'events_total': len(events),
            'errors': error_count,
            'performance_records': len(performance_data),
            'keyword_records': len(keyword_data),
            'placement_records': len(placement_data)
        }
    
    except Exception as e:
        print(f"❌ Error during import: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'events_imported': 0
        }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Import historical Google Ads data')
    parser.add_argument('--table', default=TABLE_NAME, help='DynamoDB table name')
    parser.add_argument('--start-date', default='2023-11-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-11-30', help='End date (YYYY-MM-DD)')
    parser.add_argument('--year-offset', type=int, default=1, help='Years to shift dates forward')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for progress updates')
    
    args = parser.parse_args()
    
    result = import_historical_data(
        table_name=args.table,
        start_date=args.start_date,
        end_date=args.end_date,
        year_offset=args.year_offset,
        batch_size=args.batch_size
    )
    
    if result['success']:
        print(f"\n🎉 Successfully imported {result['events_imported']} events!")
        sys.exit(0)
    else:
        print(f"\n❌ Import failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)

