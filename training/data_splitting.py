"""
Data Splitting Module for Training Data

Handles stratified sampling to split data into train/validation/test sets
while maintaining class balance.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, Any
from sklearn.model_selection import train_test_split
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def split_data(
    df: pd.DataFrame,
    train_size: float = 0.7,
    val_size: float = 0.15,
    test_size: float = 0.15,
    stratify: bool = True,
    label_column: str = 'is_fraud',
    random_state: int = 42,
    temporal_split: bool = False,
    time_column: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data into train, validation, and test sets using stratified sampling
    
    Args:
        df: DataFrame with features and labels
        train_size: Proportion for training (default: 0.7 = 70%)
        val_size: Proportion for validation (default: 0.15 = 15%)
        test_size: Proportion for testing (default: 0.15 = 15%)
        stratify: If True, use stratified sampling to maintain class balance
        label_column: Name of label column (default: 'is_fraud')
        random_state: Random seed for reproducibility
        temporal_split: If True, split by time (older = train, newer = test)
        time_column: Name of time column for temporal split (e.g., 'click_time')
    
    Returns:
        Tuple of (train_df, val_df, test_df)
    
    Raises:
        ValueError: If train_size + val_size + test_size != 1.0
        ValueError: If label_column not found
    """
    # Validate split sizes
    total_size = train_size + val_size + test_size
    if not np.isclose(total_size, 1.0, atol=1e-6):
        raise ValueError(
            f"Split sizes must sum to 1.0, got {total_size:.6f}. "
            f"train_size={train_size}, val_size={val_size}, test_size={test_size}"
        )
    
    # Validate label column exists
    if label_column not in df.columns:
        raise ValueError(f"Label column '{label_column}' not found in DataFrame")
    
    print("=" * 70)
    print("Splitting Data")
    print("=" * 70)
    print(f"Total rows: {len(df):,}")
    print(f"Split ratios: {train_size:.0%} train, {val_size:.0%} validation, {test_size:.0%} test")
    
    # Show label distribution
    if label_column in df.columns:
        label_counts = df[label_column].value_counts().sort_index()
        label_pct = df[label_column].value_counts(normalize=True).sort_index() * 100
        print(f"\nLabel distribution (original):")
        for label_val, count in label_counts.items():
            pct = label_pct[label_val]
            label_name = "fraud" if label_val == 1 else "legitimate"
            print(f"  {label_name} (label={label_val}): {count:,} ({pct:.2f}%)")
    
    # Temporal split
    if temporal_split:
        if time_column is None:
            # Try to find time column
            time_candidates = ['click_time', 'timestamp', 'time']
            time_column = next((col for col in time_candidates if col in df.columns), None)
        
        if time_column and time_column in df.columns:
            print(f"\nUsing temporal split (by {time_column})...")
            return _temporal_split(df, train_size, val_size, test_size, time_column, label_column)
        else:
            print("  ⚠️  Temporal split requested but no time column found, using random split...")
            temporal_split = False
    
    # Stratified split
    if stratify and label_column in df.columns:
        # Check if we have enough samples for each class
        label_counts = df[label_column].value_counts()
        min_class_count = label_counts.min()
        
        if min_class_count < 2:
            print(f"  ⚠️  Too few samples in minority class ({min_class_count}) for stratification")
            print("  Falling back to random split...")
            stratify = False
        else:
            print("\nUsing stratified split (maintains class balance)...")
    
    # Perform two-stage split: train vs (val+test), then val vs test
    # Stage 1: Split into train (70%) and temp (30%)
    temp_size = val_size + test_size
    try:
        if stratify:
            train_df, temp_df = train_test_split(
                df,
                test_size=temp_size,
                stratify=df[label_column],
                random_state=random_state
            )
        else:
            print("\nUsing random split...")
            train_df, temp_df = train_test_split(
                df,
                test_size=temp_size,
                random_state=random_state
            )
    except ValueError as e:
        print(f"  ⚠️  Stratified split failed: {e}")
        print("  Falling back to random split...")
        train_df, temp_df = train_test_split(
            df,
            test_size=temp_size,
            random_state=random_state
        )
    
    # Stage 2: Split temp into validation (15%) and test (15%)
    # Adjust test_size for second split: test_size / temp_size
    test_size_relative = test_size / temp_size if temp_size > 0 else 0.5
    
    try:
        if stratify and label_column in temp_df.columns:
            val_df, test_df = train_test_split(
                temp_df,
                test_size=test_size_relative,
                stratify=temp_df[label_column],
                random_state=random_state
            )
        else:
            val_df, test_df = train_test_split(
                temp_df,
                test_size=test_size_relative,
                random_state=random_state
            )
    except ValueError as e:
        print(f"  ⚠️  Stratified split failed in second stage: {e}")
        print("  Falling back to random split...")
        val_df, test_df = train_test_split(
            temp_df,
            test_size=test_size_relative,
            random_state=random_state
        )
    
    # Validate splits
    _validate_splits(train_df, val_df, test_df, label_column, train_size, val_size, test_size)
    
    print("\n" + "=" * 70)
    print("Split Complete")
    print("=" * 70)
    
    return train_df, val_df, test_df


def _temporal_split(
    df: pd.DataFrame,
    train_size: float,
    val_size: float,
    test_size: float,
    time_column: str,
    label_column: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split data temporally (older = train, newer = test)
    
    Args:
        df: DataFrame sorted by time
        train_size: Proportion for training
        val_size: Proportion for validation
        test_size: Proportion for testing
        time_column: Name of time column
        label_column: Name of label column
    
    Returns:
        Tuple of (train_df, val_df, test_df)
    """
    # Ensure time column is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
        df[time_column] = pd.to_datetime(df[time_column])
    
    # Sort by time
    df_sorted = df.sort_values(time_column).reset_index(drop=True)
    
    # Calculate split indices
    n_total = len(df_sorted)
    train_end = int(n_total * train_size)
    val_end = int(n_total * (train_size + val_size))
    
    train_df = df_sorted.iloc[:train_end].copy()
    val_df = df_sorted.iloc[train_end:val_end].copy()
    val_df = val_df.reset_index(drop=True)
    test_df = df_sorted.iloc[val_end:].copy()
    test_df = test_df.reset_index(drop=True)
    
    print(f"  Train: {len(train_df):,} rows ({train_df[time_column].min()} to {train_df[time_column].max()})")
    print(f"  Validation: {len(val_df):,} rows ({val_df[time_column].min()} to {val_df[time_column].max()})")
    print(f"  Test: {len(test_df):,} rows ({test_df[time_column].min()} to {test_df[time_column].max()})")
    
    return train_df, val_df, test_df


def _validate_splits(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    label_column: str,
    train_size: float,
    val_size: float,
    test_size: float
) -> None:
    """
    Validate that splits maintain class distribution
    
    Args:
        train_df: Training DataFrame
        val_df: Validation DataFrame
        test_df: Test DataFrame
        label_column: Name of label column
        train_size: Expected training proportion
        val_size: Expected validation proportion
        test_size: Expected test proportion
    """
    print("\nValidating splits...")
    
    # Check sizes
    n_train = len(train_df)
    n_val = len(val_df)
    n_test = len(test_df)
    n_total = n_train + n_val + n_test
    
    train_pct = n_train / n_total if n_total > 0 else 0
    val_pct = n_val / n_total if n_total > 0 else 0
    test_pct = n_test / n_total if n_total > 0 else 0
    
    print(f"  Sizes: train={n_train:,} ({train_pct:.1%}), val={n_val:,} ({val_pct:.1%}), test={n_test:,} ({test_pct:.1%})")
    
    # Check class distribution in each split
    if label_column in train_df.columns:
        print(f"\n  Class distribution:")
        
        # Original distribution (from train+val+test combined)
        all_labels = pd.concat([train_df[label_column], val_df[label_column], test_df[label_column]])
        original_dist = all_labels.value_counts(normalize=True).sort_index()
        
        for split_name, split_df in [("Train", train_df), ("Validation", val_df), ("Test", test_df)]:
            if label_column in split_df.columns:
                split_dist = split_df[label_column].value_counts(normalize=True).sort_index()
                print(f"    {split_name}:")
                for label_val in sorted(split_dist.index):
                    original_pct = original_dist.get(label_val, 0) * 100
                    split_pct = split_dist[label_val] * 100
                    label_name = "fraud" if label_val == 1 else "legitimate"
                    diff = split_pct - original_pct
                    status = "✅" if abs(diff) < 1.0 else "⚠️"
                    print(f"      {label_name}: {split_pct:.2f}% (original: {original_pct:.2f}%, diff: {diff:+.2f}%) {status}")
    
    print("  ✅ Validation complete")


def save_splits(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: Path,
    prefix: str = "data"
) -> Dict[str, Path]:
    """
    Save train/validation/test splits to CSV files
    
    Args:
        train_df: Training DataFrame
        val_df: Validation DataFrame
        test_df: Test DataFrame
        output_dir: Directory to save files
        prefix: Prefix for filenames (default: "data")
    
    Returns:
        Dictionary mapping split names to file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files = {}
    
    train_path = output_dir / f"{prefix}_train.csv"
    train_df.to_csv(train_path, index=False)
    files['train'] = train_path
    print(f"  Saved training data: {train_path} ({len(train_df):,} rows)")
    
    val_path = output_dir / f"{prefix}_val.csv"
    val_df.to_csv(val_path, index=False)
    files['validation'] = val_path
    print(f"  Saved validation data: {val_path} ({len(val_df):,} rows)")
    
    test_path = output_dir / f"{prefix}_test.csv"
    test_df.to_csv(test_path, index=False)
    files['test'] = test_path
    print(f"  Saved test data: {test_path} ({len(test_df):,} rows)")
    
    return files


def main():
    """Example usage"""
    from training.data_loader import DataLoader
    from training.feature_engineering import load_and_engineer_features
    
    # Load and engineer features
    print("Loading and engineering features...")
    if DataLoader().check_talkingdata_available():
        features_df = load_and_engineer_features(
            data_source="talkingdata",
            use_sample=True,
            nrows=1000,
            preprocess=True
        )
        
        # Split data
        train_df, val_df, test_df = split_data(
            features_df,
            train_size=0.7,
            val_size=0.15,
            test_size=0.15,
            stratify=True,
            random_state=42
        )
        
        print(f"\n✅ Split complete:")
        print(f"  Train: {len(train_df):,} rows")
        print(f"  Validation: {len(val_df):,} rows")
        print(f"  Test: {len(test_df):,} rows")
        
        # Optionally save splits
        # output_dir = Path("data/training")
        # save_splits(train_df, val_df, test_df, output_dir, prefix="talkingdata")
    else:
        print("⚠️  TalkingData files not available for testing")


if __name__ == '__main__':
    main()

