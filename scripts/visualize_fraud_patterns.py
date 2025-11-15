#!/usr/bin/env python3
"""
Create visualizations of fraud patterns
Generates charts for campaign analysis, keyword analysis, temporal patterns, and cost distribution
"""

import json
import boto3
from collections import defaultdict, Counter
from datetime import datetime
import statistics
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
import pandas as pd

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
TABLE_NAME = 'fraudguard-events-dev'

def convert_dynamodb_value(value):
    """Convert DynamoDB value to Python type"""
    if isinstance(value, dict):
        if 'S' in value:
            return value['S']
        elif 'N' in value:
            return float(value['N']) if '.' in value['N'] else int(value['N'])
        elif 'BOOL' in value:
            return value['BOOL']
        elif 'NULL' in value:
            return None
    elif isinstance(value, Decimal):
        return float(value)
    return value

def get_event_details(event_id):
    """Get full event details from DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'event_id': event_id})
        
        if 'Item' in response:
            item = response['Item']
            event = {}
            for key, value in item.items():
                event[key] = convert_dynamodb_value(value)
            return event
        return None
    except Exception as e:
        return None

def load_fraud_data():
    """Load fraud evaluation results and enrich with DynamoDB data"""
    with open('ml_evaluation_results.jsonl', 'r') as f:
        results = [json.loads(line) for line in f]
    
    fraud_events = [r for r in results if r.get('is_fraud')]
    
    enriched_data = []
    for result in fraud_events:
        event_id = result['event_id']
        event_details = get_event_details(event_id)
        
        if event_details:
            enriched_data.append({
                'event_id': event_id,
                'ml_score': result['ml_score'],
                'campaign_id': event_details.get('campaign_id', ''),
                'keyword': event_details.get('keyword', ''),
                'cost': float(event_details.get('cost_micros', 0)) / 1000000,
                'ctr': event_details.get('ctr', 0),
                'clicks': event_details.get('clicks', 0),
                'date': event_details.get('shifted_date', ''),
                'gclid': event_details.get('gclid', ''),
            })
    
    return enriched_data

def plot_campaign_analysis(df, output_dir='docs/visualizations'):
    """Create campaign-level analysis charts"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # Campaign cost and event count
    campaign_stats = df.groupby('campaign_id').agg({
        'cost': ['sum', 'count', 'mean'],
        'ctr': 'mean',
        'ml_score': 'mean'
    }).round(2)
    campaign_stats.columns = ['total_cost', 'event_count', 'avg_cost', 'avg_ctr', 'avg_ml_score']
    campaign_stats = campaign_stats.sort_values('total_cost', ascending=False).head(10)
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Campaign-Level Fraud Analysis', fontsize=16, fontweight='bold')
    
    # 1. Total Cost by Campaign
    ax1 = axes[0, 0]
    campaign_stats['total_cost'].plot(kind='barh', ax=ax1, color='#e74c3c')
    ax1.set_xlabel('Total Cost ($)', fontweight='bold')
    ax1.set_ylabel('Campaign ID', fontweight='bold')
    ax1.set_title('Total Fraud Cost by Campaign', fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    for i, v in enumerate(campaign_stats['total_cost']):
        ax1.text(v + 5, i, f'${v:.2f}', va='center')
    
    # 2. Event Count by Campaign
    ax2 = axes[0, 1]
    campaign_stats['event_count'].plot(kind='barh', ax=ax2, color='#3498db')
    ax2.set_xlabel('Number of Fraud Events', fontweight='bold')
    ax2.set_ylabel('Campaign ID', fontweight='bold')
    ax2.set_title('Fraud Event Count by Campaign', fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)
    for i, v in enumerate(campaign_stats['event_count']):
        ax2.text(v + 0.5, i, f'{int(v)}', va='center')
    
    # 3. Average CTR by Campaign
    ax3 = axes[1, 0]
    (campaign_stats['avg_ctr'] * 100).plot(kind='barh', ax=ax3, color='#f39c12')
    ax3.set_xlabel('Average CTR (%)', fontweight='bold')
    ax3.set_ylabel('Campaign ID', fontweight='bold')
    ax3.set_title('Average CTR by Campaign', fontweight='bold')
    ax3.grid(axis='x', alpha=0.3)
    for i, v in enumerate(campaign_stats['avg_ctr'] * 100):
        ax3.text(v + 0.5, i, f'{v:.2f}%', va='center')
    
    # 4. Cost vs Event Count Scatter
    ax4 = axes[1, 1]
    scatter = ax4.scatter(campaign_stats['event_count'], campaign_stats['total_cost'], 
                         s=200, alpha=0.6, c=campaign_stats['avg_ctr'] * 100, 
                         cmap='YlOrRd', edgecolors='black', linewidth=1)
    ax4.set_xlabel('Number of Fraud Events', fontweight='bold')
    ax4.set_ylabel('Total Cost ($)', fontweight='bold')
    ax4.set_title('Cost vs Event Count (Color = CTR%)', fontweight='bold')
    ax4.grid(alpha=0.3)
    plt.colorbar(scatter, ax=ax4, label='CTR (%)')
    
    # Add campaign IDs as annotations
    for idx, row in campaign_stats.iterrows():
        ax4.annotate(str(idx)[:8], (row['event_count'], row['total_cost']), 
                    fontsize=8, ha='center', va='bottom')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/campaign_analysis.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {output_dir}/campaign_analysis.png")
    plt.close()

def plot_keyword_analysis(df, output_dir='docs/visualizations'):
    """Create keyword-level analysis charts"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    keyword_stats = df[df['keyword'] != ''].groupby('keyword').agg({
        'cost': ['sum', 'count', 'mean'],
        'ctr': 'mean',
    }).round(2)
    keyword_stats.columns = ['total_cost', 'event_count', 'avg_cost', 'avg_ctr']
    keyword_stats = keyword_stats.sort_values('total_cost', ascending=False).head(15)
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    fig.suptitle('Keyword-Level Fraud Analysis', fontsize=16, fontweight='bold')
    
    # 1. Total Cost by Keyword
    ax1 = axes[0]
    keyword_stats['total_cost'].plot(kind='barh', ax=ax1, color='#e74c3c')
    ax1.set_xlabel('Total Cost ($)', fontweight='bold')
    ax1.set_ylabel('Keyword', fontweight='bold')
    ax1.set_title('Total Fraud Cost by Keyword (Top 15)', fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)
    for i, v in enumerate(keyword_stats['total_cost']):
        ax1.text(v + 2, i, f'${v:.2f}', va='center', fontsize=9)
    
    # 2. CTR Distribution by Keyword
    ax2 = axes[1]
    (keyword_stats['avg_ctr'] * 100).plot(kind='barh', ax=ax2, color='#f39c12')
    ax2.set_xlabel('Average CTR (%)', fontweight='bold')
    ax2.set_ylabel('Keyword', fontweight='bold')
    ax2.set_title('Average CTR by Keyword (Top 15)', fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)
    # Highlight suspicious CTRs (>10%)
    for i, (idx, row) in enumerate(keyword_stats.iterrows()):
        ctr_pct = row['avg_ctr'] * 100
        color = '#c0392b' if ctr_pct > 10 else '#f39c12'
        ax2.barh(i, ctr_pct, color=color, alpha=0.7)
        ax2.text(ctr_pct + 0.5, i, f'{ctr_pct:.2f}%', va='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/keyword_analysis.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {output_dir}/keyword_analysis.png")
    plt.close()

def plot_temporal_analysis(df, output_dir='docs/visualizations'):
    """Create temporal pattern charts"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert dates
    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
    df_with_dates = df.dropna(subset=['date_parsed'])
    
    # Extract hour from timestamp if available, otherwise use date
    df['hour'] = df_with_dates['date_parsed'].dt.hour if len(df_with_dates) > 0 else None
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle('Temporal Fraud Pattern Analysis', fontsize=16, fontweight='bold')
    
    # 1. Fraud Events Over Time
    ax1 = axes[0, 0]
    if len(df_with_dates) > 0:
        daily_counts = df_with_dates.groupby(df_with_dates['date_parsed'].dt.date).size()
        daily_counts.plot(kind='line', ax=ax1, marker='o', color='#e74c3c', linewidth=2, markersize=4)
        ax1.set_xlabel('Date', fontweight='bold')
        ax1.set_ylabel('Number of Fraud Events', fontweight='bold')
        ax1.set_title('Daily Fraud Event Count', fontweight='bold')
        ax1.grid(alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 2. Cumulative Cost Over Time
    ax2 = axes[0, 1]
    if len(df_with_dates) > 0:
        df_sorted = df_with_dates.sort_values('date_parsed')
        df_sorted['cumulative_cost'] = df_sorted['cost'].cumsum()
        ax2.plot(df_sorted['date_parsed'], df_sorted['cumulative_cost'], 
                color='#3498db', linewidth=2)
        ax2.fill_between(df_sorted['date_parsed'], df_sorted['cumulative_cost'], 
                        alpha=0.3, color='#3498db')
        ax2.set_xlabel('Date', fontweight='bold')
        ax2.set_ylabel('Cumulative Cost ($)', fontweight='bold')
        ax2.set_title('Cumulative Fraud Cost Over Time', fontweight='bold')
        ax2.grid(alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 3. Cost Distribution
    ax3 = axes[1, 0]
    df['cost'].hist(bins=30, ax=ax3, color='#9b59b6', edgecolor='black', alpha=0.7)
    ax3.axvline(df['cost'].mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: ${df["cost"].mean():.2f}')
    ax3.axvline(df['cost'].median(), color='orange', linestyle='--', linewidth=2, label=f'Median: ${df["cost"].median():.2f}')
    ax3.set_xlabel('Cost per Event ($)', fontweight='bold')
    ax3.set_ylabel('Frequency', fontweight='bold')
    ax3.set_title('Distribution of Fraud Event Costs', fontweight='bold')
    ax3.legend()
    ax3.grid(alpha=0.3)
    
    # 4. CTR Distribution
    ax4 = axes[1, 1]
    df['ctr_pct'] = df['ctr'] * 100
    df['ctr_pct'].hist(bins=30, ax=ax4, color='#f39c12', edgecolor='black', alpha=0.7)
    ax4.axvline(df['ctr_pct'].mean(), color='red', linestyle='--', linewidth=2, 
                label=f'Mean: {df["ctr_pct"].mean():.2f}%')
    ax4.axvline(10, color='darkred', linestyle=':', linewidth=2, label='Suspicious Threshold (10%)')
    ax4.set_xlabel('CTR (%)', fontweight='bold')
    ax4.set_ylabel('Frequency', fontweight='bold')
    ax4.set_title('Distribution of CTR Values', fontweight='bold')
    ax4.legend()
    ax4.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/temporal_analysis.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {output_dir}/temporal_analysis.png")
    plt.close()

def plot_summary_dashboard(df, output_dir='docs/visualizations'):
    """Create a comprehensive summary dashboard"""
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    fig.suptitle('Fraud Detection Summary Dashboard', fontsize=18, fontweight='bold', y=0.98)
    
    # 1. Total Cost by Campaign (Top 5)
    ax1 = fig.add_subplot(gs[0, 0])
    campaign_cost = df.groupby('campaign_id')['cost'].sum().sort_values(ascending=False).head(5)
    campaign_cost.plot(kind='bar', ax=ax1, color='#e74c3c')
    ax1.set_title('Top 5 Campaigns by Cost', fontweight='bold')
    ax1.set_ylabel('Total Cost ($)', fontweight='bold')
    ax1.set_xlabel('Campaign ID', fontweight='bold')
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(axis='y', alpha=0.3)
    
    # 2. Event Count by Campaign (Top 5)
    ax2 = fig.add_subplot(gs[0, 1])
    campaign_count = df.groupby('campaign_id').size().sort_values(ascending=False).head(5)
    campaign_count.plot(kind='bar', ax=ax2, color='#3498db')
    ax2.set_title('Top 5 Campaigns by Event Count', fontweight='bold')
    ax2.set_ylabel('Number of Events', fontweight='bold')
    ax2.set_xlabel('Campaign ID', fontweight='bold')
    ax2.tick_params(axis='x', rotation=45)
    ax2.grid(axis='y', alpha=0.3)
    
    # 3. Cost Distribution
    ax3 = fig.add_subplot(gs[0, 2])
    df['cost'].hist(bins=25, ax=ax3, color='#9b59b6', edgecolor='black', alpha=0.7)
    ax3.axvline(df['cost'].mean(), color='red', linestyle='--', linewidth=2)
    ax3.set_title('Cost Distribution', fontweight='bold')
    ax3.set_xlabel('Cost ($)', fontweight='bold')
    ax3.set_ylabel('Frequency', fontweight='bold')
    ax3.grid(alpha=0.3)
    
    # 4. CTR vs Cost Scatter
    ax4 = fig.add_subplot(gs[1, 0])
    scatter = ax4.scatter(df['ctr'] * 100, df['cost'], alpha=0.5, s=50, c=df['ml_score'], 
                         cmap='RdYlGn_r', edgecolors='black', linewidth=0.5)
    ax4.set_xlabel('CTR (%)', fontweight='bold')
    ax4.set_ylabel('Cost ($)', fontweight='bold')
    ax4.set_title('CTR vs Cost (Color = ML Score)', fontweight='bold')
    ax4.axvline(10, color='red', linestyle=':', linewidth=1, alpha=0.5, label='10% CTR Threshold')
    ax4.legend()
    ax4.grid(alpha=0.3)
    plt.colorbar(scatter, ax=ax4, label='ML Score')
    
    # 5. Top Keywords by Cost
    ax5 = fig.add_subplot(gs[1, 1])
    keyword_cost = df[df['keyword'] != ''].groupby('keyword')['cost'].sum().sort_values(ascending=False).head(8)
    keyword_cost.plot(kind='barh', ax=ax5, color='#f39c12')
    ax5.set_title('Top 8 Keywords by Cost', fontweight='bold')
    ax5.set_xlabel('Total Cost ($)', fontweight='bold')
    ax5.set_ylabel('Keyword', fontweight='bold')
    ax5.grid(axis='x', alpha=0.3)
    
    # 6. ML Score Distribution
    ax6 = fig.add_subplot(gs[1, 2])
    df['ml_score'].hist(bins=20, ax=ax6, color='#1abc9c', edgecolor='black', alpha=0.7)
    ax6.axvline(0.5, color='red', linestyle='--', linewidth=2, label='Threshold (0.5)')
    ax6.axvline(df['ml_score'].mean(), color='orange', linestyle='--', linewidth=2, 
                label=f'Mean: {df["ml_score"].mean():.4f}')
    ax6.set_title('ML Score Distribution', fontweight='bold')
    ax6.set_xlabel('ML Score', fontweight='bold')
    ax6.set_ylabel('Frequency', fontweight='bold')
    ax6.legend()
    ax6.grid(alpha=0.3)
    
    # 7. Summary Statistics Text
    ax7 = fig.add_subplot(gs[2, :])
    ax7.axis('off')
    
    stats_text = f"""
    FRAUD DETECTION SUMMARY STATISTICS
    {'='*80}
    
    Total Events Analyzed:        {len(df):,}
    Total Fraud Cost:             ${df['cost'].sum():,.2f}
    Average Cost per Event:      ${df['cost'].mean():.2f}
    Median Cost per Event:        ${df['cost'].median():.2f}
    Highest Single Event Cost:   ${df['cost'].max():.2f}
    
    Average CTR:                 {df['ctr'].mean()*100:.2f}%
    Median CTR:                  {df['ctr'].median()*100:.2f}%
    Highest CTR:                 {df['ctr'].max()*100:.2f}%
    Events with CTR > 10%:        {len(df[df['ctr'] > 0.10]):,} ({len(df[df['ctr'] > 0.10])/len(df)*100:.1f}%)
    
    Average ML Score:            {df['ml_score'].mean():.4f}
    ML Score Range:              {df['ml_score'].min():.4f} - {df['ml_score'].max():.4f}
    
    Top Campaign (by cost):      {df.groupby('campaign_id')['cost'].sum().idxmax()} (${df.groupby('campaign_id')['cost'].sum().max():,.2f})
    Top Campaign (by count):     {df.groupby('campaign_id').size().idxmax()} ({df.groupby('campaign_id').size().max()} events)
    """
    
    ax7.text(0.05, 0.5, stats_text, fontsize=11, family='monospace', 
            verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.savefig(f'{output_dir}/summary_dashboard.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {output_dir}/summary_dashboard.png")
    plt.close()

def main():
    """Main function to generate all visualizations"""
    print("=" * 80)
    print("FRAUD PATTERN VISUALIZATION GENERATOR")
    print("=" * 80)
    print("\n📊 Loading fraud data...")
    
    try:
        data = load_fraud_data()
        df = pd.DataFrame(data)
        
        print(f"✅ Loaded {len(df)} fraud events")
        print(f"\n📈 Generating visualizations...")
        
        plot_campaign_analysis(df)
        plot_keyword_analysis(df)
        plot_temporal_analysis(df)
        plot_summary_dashboard(df)
        
        print("\n" + "=" * 80)
        print("✅ ALL VISUALIZATIONS GENERATED SUCCESSFULLY")
        print("=" * 80)
        print("\n📁 Output directory: docs/visualizations/")
        print("   - campaign_analysis.png")
        print("   - keyword_analysis.png")
        print("   - temporal_analysis.png")
        print("   - summary_dashboard.png")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    from decimal import Decimal
    main()

