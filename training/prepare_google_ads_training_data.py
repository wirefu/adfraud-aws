#!/usr/bin/env python3
"""
Prepare Google Ads Data for Training with Soft Labels

This script addresses the issue of potentially undetected fraud by:
1. Creating soft labels from fraud scores (instead of hard binary labels)
2. Applying sample weights based on confidence
3. Identifying suspicious cases for potential relabeling
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Tuple, List, Optional
from sklearn.model_selection import train_test_split

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.data_loader import DataLoader


def create_soft_label(item: Dict) -> Tuple[float, float]:
    """
    Create soft label and weight from fraud detection data
    
    Args:
        item: Event dictionary from DynamoDB
    
    Returns:
        Tuple of (label, weight) where:
        - label: Soft fraud label (0.0-1.0)
        - weight: Sample weight for training (0.0-1.0)
    """
    fraud_score = float(item.get('fraud_score', 0))
    is_fraud_hard = item.get('is_fraud', False)
    fraud_signals = item.get('fraud_signals', [])
    signal_count = len(fraud_signals) if isinstance(fraud_signals, list) else 0
    
    # Hard label if explicitly marked as fraud
    if is_fraud_hard:
        return 1.0, 1.0
    
    # High confidence fraud (score > 0.7)
    if fraud_score > 0.7:
        return 1.0, 1.0
    
    # Medium-high confidence (0.5-0.7) - likely fraud but not certain
    elif fraud_score > 0.5:
        return fraud_score, 0.8
    
    # Medium confidence (0.4-0.5) - suspicious
    elif fraud_score > 0.4:
        return fraud_score, 0.5
    
    # Low-medium confidence (0.3-0.4) - slightly suspicious
    elif fraud_score > 0.3:
        # Boost if multiple signals
        if signal_count >= 2:
            return fraud_score * 0.7, 0.4
        else:
            return fraud_score * 0.5, 0.3
    
    # Low confidence (0.0-0.3) - likely legitimate
    else:
        return 0.0, 1.0


def should_relabel_as_fraud(item: Dict) -> bool:
    """
    Determine if item should be relabeled as fraud based on rules
    
    Args:
        item: Event dictionary
    
    Returns:
        True if item should be relabeled as fraud
    """
    fraud_score = float(item.get('fraud_score', 0))
    signals = item.get('fraud_signals', [])
    signal_count = len(signals) if isinstance(signals, list) else 0
    is_fraud = item.get('is_fraud', False)
    
    # Already labeled as fraud
    if is_fraud:
        return False
    
    # Rule 1: High score with multiple signals
    if fraud_score > 0.45 and signal_count >= 3:
        return True
    
    # Rule 2: Multiple strong fraud signals
    strong_signals = [
        'datacenter_ip',
        'headless_browser',
        'impersonated_device',
        'impersonated_device_id',
        'bot_user_agent'
    ]
    strong_signal_count = sum(1 for s in signals if s in strong_signals)
    if strong_signal_count >= 2:
        return True
    
    # Rule 3: High score with specific fraud type indicators
    if fraud_score > 0.4 and any(s in signals for s in [
        'low_device_entropy',
        'low_device_fingerprint_entropy',
        'suspicious_publisher'
    ]):
        return True
    
    return False


def prepare_training_data(
    use_soft_labels: bool = True,
    apply_relabeling: bool = False,
    output_path: Path = None,
    test_size: float = 0.3,
    random_state: int = 42,
    stratify: bool = True,
    temporal_split: bool = False
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
    """
    Prepare Google Ads data for training with optional train/test split
    
    Args:
        use_soft_labels: If True, use soft labels from fraud scores
        apply_relabeling: If True, apply rule-based relabeling
        output_path: Optional path to save prepared data (if None, returns both train and test)
        test_size: Proportion of data to use for testing (0.0-1.0). If 0.0, no split is performed.
        random_state: Random seed for reproducibility
        stratify: If True, use stratified sampling to maintain class balance
        temporal_split: If True, split by timestamp (older = train, newer = test)
    
    Returns:
        Tuple of (train_df, test_df). If test_size=0.0, test_df will be None.
    """
    loader = DataLoader()
    
    print("Loading Google Ads data from DynamoDB...")
    df = loader.load_google_ads_data()
    
    print(f"\nLoaded {len(df):,} items")
    
    # Convert to DataFrame if needed (DynamoDB items are dicts)
    if isinstance(df, pd.DataFrame) and len(df) > 0:
        # If already a DataFrame, ensure it has the right structure
        if 'fraud_score' not in df.columns:
            # Convert from dict format
            df = pd.DataFrame([item for item in df.to_dict('records')])
    else:
        # Convert list of dicts to DataFrame
        df = pd.DataFrame(df)
    
    print(f"\nPreparing labels...")
    
    # Apply relabeling if requested
    if apply_relabeling:
        print("Applying rule-based relabeling...")
        relabeled_count = 0
        for idx, row in df.iterrows():
            item = row.to_dict()
            if should_relabel_as_fraud(item):
                df.at[idx, 'is_fraud'] = True
                df.at[idx, 'relabeled'] = True
                relabeled_count += 1
        print(f"  Relabeled {relabeled_count} items as fraud")
    else:
        df['relabeled'] = False
    
    # Create labels
    if use_soft_labels:
        print("Creating soft labels from fraud scores...")
        labels_and_weights = df.apply(
            lambda row: create_soft_label(row.to_dict()),
            axis=1
        )
        df['fraud_label'] = [lw[0] for lw in labels_and_weights]
        df['sample_weight'] = [lw[1] for lw in labels_and_weights]
        label_type = "soft"
    else:
        print("Using hard binary labels...")
        df['fraud_label'] = df['is_fraud'].astype(float)
        df['sample_weight'] = 1.0
        label_type = "hard"
    
    # Statistics
    print(f"\n{'='*70}")
    print(f"Training Data Summary ({label_type} labels)")
    print(f"{'='*70}")
    
    if use_soft_labels:
        fraud_count = (df['fraud_label'] > 0.5).sum()
        suspicious_count = ((df['fraud_label'] > 0.3) & (df['fraud_label'] <= 0.5)).sum()
        legit_count = (df['fraud_label'] <= 0.3).sum()
        
        print(f"\nLabel Distribution:")
        print(f"  High confidence fraud (label > 0.5): {fraud_count:,} ({fraud_count/len(df)*100:.2f}%)")
        print(f"  Suspicious (0.3 < label <= 0.5): {suspicious_count:,} ({suspicious_count/len(df)*100:.2f}%)")
        print(f"  Legitimate (label <= 0.3): {legit_count:,} ({legit_count/len(df)*100:.2f}%)")
        
        print(f"\nSample Weight Distribution:")
        print(f"  Mean weight: {df['sample_weight'].mean():.3f}")
        print(f"  Min weight: {df['sample_weight'].min():.3f}")
        print(f"  Max weight: {df['sample_weight'].max():.3f}")
    else:
        fraud_count = (df['fraud_label'] == 1.0).sum()
        legit_count = (df['fraud_label'] == 0.0).sum()
        
        print(f"\nLabel Distribution:")
        print(f"  Fraud: {fraud_count:,} ({fraud_count/len(df)*100:.2f}%)")
        print(f"  Legitimate: {legit_count:,} ({legit_count/len(df)*100:.2f}%)")
    
    # Relabeling stats
    if apply_relabeling:
        relabeled = df['relabeled'].sum()
        print(f"\nRelabeling:")
        print(f"  Items relabeled: {relabeled:,}")
    
    # Perform train/test split if requested
    test_df = None
    if test_size > 0.0:
        print(f"\n{'='*70}")
        print(f"Splitting data: {1-test_size:.0%} train, {test_size:.0%} test")
        print(f"{'='*70}")
        
        # Prepare for splitting
        if temporal_split and 'timestamp' in df.columns:
            print("Using temporal split (by timestamp)...")
            # Sort by timestamp
            df_sorted = df.sort_values('timestamp')
            split_idx = int(len(df_sorted) * (1 - test_size))
            train_df = df_sorted.iloc[:split_idx].copy()
            test_df = df_sorted.iloc[split_idx:].copy()
        else:
            # Use stratified split if possible
            if stratify and 'is_fraud' in df.columns:
                # Check if we have enough fraud cases for stratification
                fraud_count = df['is_fraud'].sum()
                if fraud_count >= 2:  # Need at least 2 fraud cases for stratification
                    print("Using stratified split (maintains class balance)...")
                    try:
                        train_df, test_df = train_test_split(
                            df,
                            test_size=test_size,
                            stratify=df['is_fraud'],
                            random_state=random_state
                        )
                    except ValueError as e:
                        print(f"  ⚠️  Stratified split failed: {e}")
                        print("  Falling back to random split...")
                        train_df, test_df = train_test_split(
                            df,
                            test_size=test_size,
                            random_state=random_state
                        )
                else:
                    print("  ⚠️  Too few fraud cases for stratification, using random split...")
                    train_df, test_df = train_test_split(
                        df,
                        test_size=test_size,
                        random_state=random_state
                    )
            else:
                print("Using random split...")
                train_df, test_df = train_test_split(
                    df,
                    test_size=test_size,
                    random_state=random_state
                )
        
        # Print split statistics
        print(f"\nTraining set: {len(train_df):,} items")
        if use_soft_labels:
            train_fraud = (train_df['fraud_label'] > 0.5).sum()
            train_suspicious = ((train_df['fraud_label'] > 0.3) & (train_df['fraud_label'] <= 0.5)).sum()
            print(f"  High confidence fraud: {train_fraud:,}")
            print(f"  Suspicious: {train_suspicious:,}")
        else:
            train_fraud = (train_df['fraud_label'] == 1.0).sum()
            print(f"  Fraud: {train_fraud:,}")
        
        print(f"\nTest set: {len(test_df):,} items")
        if use_soft_labels:
            test_fraud = (test_df['fraud_label'] > 0.5).sum()
            test_suspicious = ((test_df['fraud_label'] > 0.3) & (test_df['fraud_label'] <= 0.5)).sum()
            print(f"  High confidence fraud: {test_fraud:,}")
            print(f"  Suspicious: {test_suspicious:,}")
        else:
            test_fraud = (test_df['fraud_label'] == 1.0).sum()
            print(f"  Fraud: {test_fraud:,}")
        
        # Save split data if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save training data
            train_path = output_path.parent / f"{output_path.stem}_train.csv"
            train_df.to_csv(train_path, index=False)
            print(f"\n✅ Saved training data to: {train_path}")
            
            # Save test data
            test_path = output_path.parent / f"{output_path.stem}_test.csv"
            test_df.to_csv(test_path, index=False)
            print(f"✅ Saved test data to: {test_path}")
        
        return train_df, test_df
    else:
        # No split requested
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n✅ Saved prepared data to: {output_path}")
        
        return df, None


def identify_suspicious_cases(df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    """
    Identify most suspicious cases for potential manual review
    
    Args:
        df: DataFrame with event data
        top_n: Number of top suspicious cases to return
    
    Returns:
        DataFrame with top suspicious cases
    """
    # Calculate suspicion score
    def suspicion_score(row):
        fraud_score = float(row.get('fraud_score', 0))
        signals = row.get('fraud_signals', [])
        signal_count = len(signals) if isinstance(signals, list) else 0
        is_fraud = row.get('is_fraud', False)
        
        # Skip already labeled fraud
        if is_fraud:
            return 0
        
        # Uncertainty score (highest at 0.5)
        uncertainty = 1 - abs(fraud_score - 0.5) * 2
        
        # Signal count bonus
        signal_bonus = min(signal_count / 5, 1.0)
        
        # Combined score
        score = (uncertainty * 0.4 + signal_bonus * 0.3 + fraud_score * 0.3)
        return score
    
    df['suspicion_score'] = df.apply(suspicion_score, axis=1)
    
    # Get top suspicious cases
    suspicious = df.nlargest(top_n, 'suspicion_score')
    
    return suspicious[['event_id', 'fraud_score', 'fraud_signals', 'is_fraud', 
                       'suspicion_score', 'campaign_name', 'timestamp']]


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Prepare Google Ads data for training'
    )
    parser.add_argument(
        '--soft-labels',
        action='store_true',
        default=True,
        help='Use soft labels from fraud scores (default: True)'
    )
    parser.add_argument(
        '--hard-labels',
        action='store_true',
        help='Use hard binary labels instead of soft labels'
    )
    parser.add_argument(
        '--relabel',
        action='store_true',
        help='Apply rule-based relabeling for suspicious cases'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output path for prepared data CSV'
    )
    parser.add_argument(
        '--suspicious',
        type=int,
        metavar='N',
        help='Identify top N suspicious cases for review'
    )
    parser.add_argument(
        '--test-size',
        type=float,
        default=0.3,
        help='Proportion of data for testing (default: 0.3 = 30%%)'
    )
    parser.add_argument(
        '--no-stratify',
        action='store_true',
        help='Disable stratified sampling (use random split)'
    )
    parser.add_argument(
        '--temporal-split',
        action='store_true',
        help='Split by timestamp (older = train, newer = test) instead of random'
    )
    parser.add_argument(
        '--random-state',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    args = parser.parse_args()
    
    # Determine label type
    use_soft = args.soft_labels and not args.hard_labels
    
    # Prepare data with train/test split
    train_df, test_df = prepare_training_data(
        use_soft_labels=use_soft,
        apply_relabeling=args.relabel,
        output_path=args.output,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=not args.no_stratify,
        temporal_split=args.temporal_split
    )
    
    # Identify suspicious cases if requested (use training data only)
    if args.suspicious:
        print(f"\n{'='*70}")
        print(f"Top {args.suspicious} Suspicious Cases for Review (from training set)")
        print(f"{'='*70}")
        suspicious = identify_suspicious_cases(train_df, top_n=args.suspicious)
        print(f"\n{suspicious.to_string()}")
        
        # Save suspicious cases
        if args.output:
            suspicious_path = Path(args.output).parent / 'suspicious_cases.csv'
            suspicious.to_csv(suspicious_path, index=False)
            print(f"\n✅ Saved suspicious cases to: {suspicious_path}")


if __name__ == '__main__':
    main()

