"""
Data Loading Module for Training

Loads data from multiple sources:
- TalkingData AdTracking Fraud Detection (CSV files)
- FDB (Fraud Dataset Benchmark) datasets
- Synthetic data
- Google Ads historical data (DynamoDB)

All data is returned in a consistent pandas DataFrame format.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import logging

import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
TALKINGDATA_DIR = DATA_DIR / "talkingdata"
FDB_DIR = DATA_DIR / "fdb"
SYNTHETIC_DIR = DATA_DIR / "synthetic"

# Default chunk size for large CSV files (10MB chunks)
DEFAULT_CHUNK_SIZE = 100000


class DataLoader:
    """
    Load training data from multiple sources
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize data loader
        
        Args:
            data_dir: Optional custom data directory path
        """
        self.data_dir = data_dir or DATA_DIR
        self.talkingdata_dir = self.data_dir / "talkingdata"
        self.fdb_dir = self.data_dir / "fdb"
        self.synthetic_dir = self.data_dir / "synthetic"
        
        # Ensure directories exist
        for dir_path in [self.data_dir, self.talkingdata_dir, self.fdb_dir, self.synthetic_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def check_talkingdata_available(self) -> bool:
        """
        Check if TalkingData files are available
        
        Returns:
            True if TalkingData files exist, False otherwise
        """
        train_file = self.talkingdata_dir / "train.csv"
        train_sample_file = self.talkingdata_dir / "train_sample.csv"
        
        return train_file.exists() or train_sample_file.exists()
    
    def check_fdb_available(self) -> bool:
        """
        Check if FDB package is available and datasets can be loaded
        
        Returns:
            True if FDB is available, False otherwise
        """
        try:
            import fdb
            from fdb.datasets import FraudDatasetBenchmark
            return True
        except ImportError:
            return False
    
    def check_synthetic_available(self) -> bool:
        """
        Check if synthetic data files are available
        
        Returns:
            True if synthetic data exists, False otherwise
        """
        synthetic_file = self.synthetic_dir / "training_data.csv"
        return synthetic_file.exists()
    
    def load_talkingdata(
        self,
        use_sample: bool = True,
        nrows: Optional[int] = None,
        chunk_size: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load TalkingData AdTracking Fraud Detection dataset
        
        Args:
            use_sample: If True, use train_sample.csv (smaller, faster). If False, use train.csv
            nrows: Number of rows to read (None = all rows). Only used if chunk_size is None
            chunk_size: If provided, read in chunks and return concatenated result
        
        Returns:
            DataFrame with TalkingData columns:
            - ip: IP address (integer encoded)
            - app: App ID
            - device: Device ID
            - os: Operating system version
            - channel: Channel ID
            - click_time: Timestamp of click
            - attributed_time: Timestamp of attribution (if attributed)
            - is_attributed: Label (0 = fraud, 1 = legitimate)
        
        Raises:
            FileNotFoundError: If TalkingData files are not found
        """
        if use_sample:
            file_path = self.talkingdata_dir / "train_sample.csv"
            if not file_path.exists():
                # Fallback to full train.csv if sample doesn't exist
                file_path = self.talkingdata_dir / "train.csv"
                logger.warning(f"train_sample.csv not found, using train.csv instead")
        else:
            file_path = self.talkingdata_dir / "train.csv"
        
        if not file_path.exists():
            raise FileNotFoundError(
                f"TalkingData file not found: {file_path}\n"
                f"Please download it using: python3 scripts/download_talkingdata_kaggle.py"
            )
        
        logger.info(f"Loading TalkingData from: {file_path}")
        
        # Read in chunks if chunk_size is provided (for large files)
        if chunk_size:
            logger.info(f"Reading in chunks of {chunk_size} rows...")
            chunks = []
            for chunk in pd.read_csv(file_path, chunksize=chunk_size, nrows=nrows):
                chunks.append(chunk)
                if nrows and len(pd.concat(chunks, ignore_index=True)) >= nrows:
                    break
            
            df = pd.concat(chunks, ignore_index=True)
            if nrows:
                df = df.head(nrows)
        else:
            # Read entire file (or nrows if specified)
            df = pd.read_csv(file_path, nrows=nrows)
        
        logger.info(f"Loaded {len(df):,} rows from TalkingData")
        logger.info(f"Columns: {list(df.columns)}")
        
        # Convert click_time to datetime if present
        if 'click_time' in df.columns:
            df['click_time'] = pd.to_datetime(df['click_time'])
        
        # Convert attributed_time to datetime if present
        if 'attributed_time' in df.columns:
            df['attributed_time'] = pd.to_datetime(df['attributed_time'])
        
        # Map label: is_attributed=0 means fraud, is_attributed=1 means legitimate
        # We'll keep is_attributed for now, feature engineering will handle conversion
        if 'is_attributed' in df.columns:
            logger.info(f"Label distribution:")
            logger.info(f"  is_attributed=0 (fraud): {(df['is_attributed'] == 0).sum():,} ({(df['is_attributed'] == 0).mean()*100:.2f}%)")
            logger.info(f"  is_attributed=1 (legitimate): {(df['is_attributed'] == 1).sum():,} ({(df['is_attributed'] == 1).mean()*100:.2f}%)")
        
        return df
    
    def load_fdb_dataset(
        self,
        dataset_key: str = "ccfraud",
        split: str = "train"
    ) -> pd.DataFrame:
        """
        Load FDB (Fraud Dataset Benchmark) dataset
        
        Args:
            dataset_key: Dataset identifier (e.g., "ccfraud", "ieeecis", "sparkov")
            split: "train" or "test"
        
        Returns:
            DataFrame with dataset-specific columns
        
        Raises:
            ImportError: If FDB package is not available
            ValueError: If dataset_key is invalid
        """
        try:
            from fdb.datasets import FraudDatasetBenchmark
        except ImportError:
            raise ImportError(
                "FDB package not available. Install it using:\n"
                "  python3 scripts/download_fdb_dataset.py"
            )
        
        logger.info(f"Loading FDB dataset: {dataset_key} (split: {split})")
        
        try:
            obj = FraudDatasetBenchmark(key=dataset_key)
            
            if split == "train":
                df = obj.train
            elif split == "test":
                df = obj.test
            else:
                raise ValueError(f"Invalid split: {split}. Must be 'train' or 'test'")
            
            logger.info(f"Loaded {len(df):,} rows from FDB dataset {dataset_key}")
            logger.info(f"Columns: {list(df.columns)}")
            
            return df
            
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "Forbidden" in error_msg:
                raise ValueError(
                    f"Access denied for dataset {dataset_key}. "
                    f"You may need to join the Kaggle competition first."
                )
            elif "401" in error_msg or "Unauthorized" in error_msg:
                raise ValueError(
                    f"Unauthorized access. Please check your Kaggle credentials."
                )
            else:
                raise ValueError(f"Error loading FDB dataset {dataset_key}: {error_msg}")
    
    def load_synthetic_data(
        self,
        filename: str = "training_data.csv"
    ) -> pd.DataFrame:
        """
        Load synthetic training data
        
        Args:
            filename: Name of the synthetic data file
        
        Returns:
            DataFrame with synthetic training data
        
        Raises:
            FileNotFoundError: If synthetic data file is not found
        """
        file_path = self.synthetic_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(
                f"Synthetic data file not found: {file_path}\n"
                f"Please generate it first using the synthetic data generation script."
            )
        
        logger.info(f"Loading synthetic data from: {file_path}")
        
        df = pd.read_csv(file_path)
        
        logger.info(f"Loaded {len(df):,} rows from synthetic data")
        logger.info(f"Columns: {list(df.columns)}")
        
        # Check for label column
        if 'is_fraud' in df.columns:
            logger.info(f"Label distribution:")
            logger.info(f"  is_fraud=0 (legitimate): {(df['is_fraud'] == 0).sum():,} ({(df['is_fraud'] == 0).mean()*100:.2f}%)")
            logger.info(f"  is_fraud=1 (fraud): {(df['is_fraud'] == 1).sum():,} ({(df['is_fraud'] == 1).mean()*100:.2f}%)")
        
        return df
    
    def load_google_ads_data(
        self,
        table_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load Google Ads historical data from DynamoDB
        
        Args:
            table_name: DynamoDB table name (defaults to environment variable)
            limit: Maximum number of records to load (None = all)
        
        Returns:
            DataFrame with Google Ads event data
        
        Raises:
            ImportError: If boto3 is not available
            ValueError: If table_name is not provided and not in environment
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise ImportError("boto3 is required to load Google Ads data from DynamoDB")
        
        # Get table name from environment or parameter
        if not table_name:
            table_name = os.environ.get("TABLE_NAME")
            if not table_name:
                raise ValueError(
                    "Table name not provided. Set TABLE_NAME environment variable "
                    "or pass table_name parameter."
                )
        
        logger.info(f"Loading Google Ads data from DynamoDB table: {table_name}")
        
        try:
            dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
            table = dynamodb.Table(table_name)
            
            # Scan table (for small tables) or use query with pagination
            items = []
            response = table.scan()
            items.extend(response.get('Items', []))
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                if limit and len(items) >= limit:
                    break
                response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                items.extend(response.get('Items', []))
            
            # Limit results if specified
            if limit:
                items = items[:limit]
            
            if not items:
                logger.warning(f"No items found in DynamoDB table: {table_name}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(items)
            
            logger.info(f"Loaded {len(df):,} rows from Google Ads DynamoDB table")
            logger.info(f"Columns: {list(df.columns)}")
            
            return df
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'ResourceNotFoundException':
                raise ValueError(f"DynamoDB table not found: {table_name}")
            else:
                raise ValueError(f"Error loading from DynamoDB: {error_code} - {str(e)}")
    
    def get_available_data_sources(self) -> Dict[str, bool]:
        """
        Check which data sources are available
        
        Returns:
            Dictionary mapping source names to availability status
        """
        return {
            "talkingdata": self.check_talkingdata_available(),
            "fdb": self.check_fdb_available(),
            "synthetic": self.check_synthetic_available(),
            "google_ads": os.environ.get("TABLE_NAME") is not None
        }
    
    def load_all_available(
        self,
        talkingdata_sample: bool = True,
        talkingdata_nrows: Optional[int] = None,
        fdb_datasets: Optional[List[str]] = None,
        google_ads_limit: Optional[int] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load all available data sources
        
        Args:
            talkingdata_sample: Use sample file for TalkingData
            talkingdata_nrows: Limit rows for TalkingData
            fdb_datasets: List of FDB dataset keys to load (None = skip)
            google_ads_limit: Limit records for Google Ads (None = skip)
        
        Returns:
            Dictionary mapping source names to DataFrames
        """
        results = {}
        available = self.get_available_data_sources()
        
        # Load TalkingData if available
        if available["talkingdata"]:
            try:
                results["talkingdata"] = self.load_talkingdata(
                    use_sample=talkingdata_sample,
                    nrows=talkingdata_nrows
                )
            except Exception as e:
                logger.error(f"Error loading TalkingData: {str(e)}")
        
        # Load FDB datasets if requested and available
        if fdb_datasets and available["fdb"]:
            for dataset_key in fdb_datasets:
                try:
                    df = self.load_fdb_dataset(dataset_key, split="train")
                    results[f"fdb_{dataset_key}"] = df
                except Exception as e:
                    logger.error(f"Error loading FDB dataset {dataset_key}: {str(e)}")
        
        # Load synthetic data if available
        if available["synthetic"]:
            try:
                results["synthetic"] = self.load_synthetic_data()
            except Exception as e:
                logger.error(f"Error loading synthetic data: {str(e)}")
        
        # Load Google Ads data if requested and available
        if google_ads_limit and available["google_ads"]:
            try:
                results["google_ads"] = self.load_google_ads_data(limit=google_ads_limit)
            except Exception as e:
                logger.error(f"Error loading Google Ads data: {str(e)}")
        
        return results


def main():
    """
    Example usage of DataLoader
    """
    loader = DataLoader()
    
    # Check available sources
    print("=" * 70)
    print("Available Data Sources")
    print("=" * 70)
    available = loader.get_available_data_sources()
    for source, is_available in available.items():
        status = "✅ Available" if is_available else "❌ Not Available"
        print(f"{source:20s}: {status}")
    print()
    
    # Try loading TalkingData (sample)
    if available["talkingdata"]:
        print("=" * 70)
        print("Loading TalkingData (sample)")
        print("=" * 70)
        try:
            df = loader.load_talkingdata(use_sample=True, nrows=1000)
            print(f"\n✅ Successfully loaded {len(df):,} rows")
            print(f"\nFirst few rows:")
            print(df.head())
            print(f"\nDataFrame info:")
            print(df.info())
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
    
    # Try loading synthetic data if available
    if available["synthetic"]:
        print("\n" + "=" * 70)
        print("Loading Synthetic Data")
        print("=" * 70)
        try:
            df = loader.load_synthetic_data()
            print(f"\n✅ Successfully loaded {len(df):,} rows")
            print(f"\nFirst few rows:")
            print(df.head())
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    main()

