#!/usr/bin/env python3
"""
Download FDB (Fraud Dataset Benchmark) from Amazon Science
https://github.com/amazon-science/fraud-dataset-benchmark

FDB is a Python package that provides dataset loaders for fraud detection datasets.
This script:
1. Clones the FDB repository from GitHub
2. Installs it as a Python package
3. Downloads datasets using FDB's API (requires Kaggle credentials)
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, List

# Configuration
FDB_GITHUB_URL = "https://github.com/amazon-science/fraud-dataset-benchmark.git"
FDB_REPO_DIR = Path(__file__).parent.parent / "data" / "fdb" / "fraud-dataset-benchmark"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "fdb"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Kaggle credentials path
KAGGLE_CREDENTIALS_PATHS = [
    Path.home() / ".kaggle" / "kaggle.json",
    Path(__file__).parent.parent / "kaggle" / "kaggle.json",
]

# Available FDB datasets
FDB_DATASETS = [
    "ieeecis",      # IEEE-CIS Fraud Detection
    "ccfraud",      # Credit Card Fraud Detection
    "fraudecommerce",  # Fraud ecommerce
    "sparkov",      # Simulated Credit Card Transactions
    "twitterbot",   # Twitter Bot Accounts
    "maliciousurl", # Malicious URLs
    "fakejob",      # Fake Job Posting Prediction
    "vehicleloan",  # Vehicle Loan Default Prediction
    "ipblocklist", # IP Blocklist
]


def check_git_available() -> bool:
    """
    Check if git is available
    """
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_kaggle_credentials() -> Optional[Path]:
    """
    Check if Kaggle credentials are available
    """
    for cred_path in KAGGLE_CREDENTIALS_PATHS:
        if cred_path.exists():
            try:
                with open(cred_path, 'r') as f:
                    creds = json.load(f)
                    if 'username' in creds and 'key' in creds:
                        print(f"✅ Found Kaggle credentials at: {cred_path}")
                        # Set environment variable for kaggle CLI
                        os.environ['KAGGLE_CONFIG_DIR'] = str(cred_path.parent)
                        return cred_path
            except Exception as e:
                print(f"⚠️  Error reading credentials from {cred_path}: {str(e)}")
                continue
    
    return None


def clone_fdb_repository() -> bool:
    """
    Clone FDB repository from GitHub
    """
    if FDB_REPO_DIR.exists():
        print(f"✅ FDB repository already exists at: {FDB_REPO_DIR}")
        print("   Updating repository...")
        try:
            subprocess.run(
                ["git", "pull"],
                cwd=FDB_REPO_DIR,
                check=True,
                capture_output=True
            )
            print("✅ Repository updated")
            return True
        except subprocess.CalledProcessError:
            print("⚠️  Could not update, using existing repository")
            return True
    
    print(f"📥 Cloning FDB repository from GitHub...")
    print(f"   URL: {FDB_GITHUB_URL}")
    print(f"   Destination: {FDB_REPO_DIR}")
    
    try:
        subprocess.run(
            ["git", "clone", FDB_GITHUB_URL, str(FDB_REPO_DIR)],
            check=True,
            capture_output=True
        )
        print("✅ Repository cloned successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error cloning repository: {str(e)}")
        if e.stderr:
            print(f"   Error details: {e.stderr.decode()}")
        return False


def install_fdb_package() -> bool:
    """
    Install FDB as a Python package
    """
    if not FDB_REPO_DIR.exists():
        print("❌ FDB repository not found. Please clone it first.")
        return False
    
    setup_py = FDB_REPO_DIR / "setup.py"
    if not setup_py.exists():
        print("❌ setup.py not found in FDB repository")
        return False
    
    print("📦 Installing FDB package...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(FDB_REPO_DIR)],
            check=True,
            capture_output=True
        )
        print("✅ FDB package installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing FDB package: {str(e)}")
        if e.stderr:
            print(f"   Error details: {e.stderr.decode()}")
        return False


def check_fdb_import() -> bool:
    """
    Check if FDB can be imported
    """
    try:
        import fdb
        print("✅ FDB package is available")
        return True
    except ImportError:
        print("❌ FDB package not found. Please install it first.")
        return False


def download_fdb_datasets(datasets: Optional[List[str]] = None) -> bool:
    """
    Download FDB datasets using the FDB API
    Note: This requires Kaggle credentials and may require joining competitions
    """
    if not check_fdb_import():
        return False
    
    if datasets is None:
        datasets = FDB_DATASETS
    
    print(f"\n📥 Downloading {len(datasets)} FDB dataset(s)...")
    print("   Note: This may require Kaggle API credentials and joining competitions")
    print("   Some datasets may take a while to download\n")
    
    try:
        from fdb.datasets import FraudDatasetBenchmark
        
        results = {}
        for dataset_key in datasets:
            print(f"\n{'='*60}")
            print(f"Downloading: {dataset_key}")
            print(f"{'='*60}")
            
            try:
                obj = FraudDatasetBenchmark(key=dataset_key)
                print(f"✅ Successfully loaded {dataset_key}")
                print(f"   Train samples: {len(obj.train) if hasattr(obj, 'train') else 'N/A'}")
                print(f"   Test samples: {len(obj.test) if hasattr(obj, 'test') else 'N/A'}")
                results[dataset_key] = "success"
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Error loading {dataset_key}: {error_msg}")
                
                if "403" in error_msg or "Forbidden" in error_msg:
                    print("   ⚠️  You may need to join the Kaggle competition")
                    print(f"   Visit: https://www.kaggle.com/competitions/{dataset_key}")
                elif "401" in error_msg or "Unauthorized" in error_msg:
                    print("   ⚠️  Check your Kaggle credentials")
                
                results[dataset_key] = f"error: {error_msg}"
        
        # Print summary
        print(f"\n{'='*60}")
        print("Download Summary")
        print(f"{'='*60}")
        successful = sum(1 for v in results.values() if v == "success")
        print(f"✅ Successful: {successful}/{len(datasets)}")
        print(f"❌ Failed: {len(datasets) - successful}/{len(datasets)}")
        
        return successful > 0
        
    except ImportError as e:
        print(f"❌ Error importing FDB: {str(e)}")
        print("   Make sure FDB is properly installed")
        return False
    except Exception as e:
        print(f"❌ Error downloading datasets: {str(e)}")
        return False


def list_available_datasets() -> None:
    """
    List all available FDB datasets
    """
    print("\n📊 Available FDB Datasets:")
    print("=" * 60)
    dataset_info = {
        "ieeecis": "IEEE-CIS Fraud Detection (561,013 train, 3.50% fraud)",
        "ccfraud": "Credit Card Fraud Detection (227,845 train, 0.18% fraud)",
        "fraudecommerce": "Fraud ecommerce (120,889 train, 10.60% fraud)",
        "sparkov": "Simulated Credit Card Transactions (1,296,675 train, 5.70% fraud)",
        "twitterbot": "Twitter Bot Accounts (29,950 train, 33.10% fraud)",
        "maliciousurl": "Malicious URLs (586,072 train, 34.20% fraud)",
        "fakejob": "Fake Job Posting Prediction (14,304 train, 4.70% fraud)",
        "vehicleloan": "Vehicle Loan Default Prediction (186,523 train, 21.60% fraud)",
        "ipblocklist": "IP Blocklist (172,000 train, 7% fraud)",
    }
    
    for i, (key, desc) in enumerate(dataset_info.items(), 1):
        print(f"{i}. {key:20s} - {desc}")


def main():
    """
    Main function to download FDB
    """
    print("=" * 70)
    print("FDB (Fraud Dataset Benchmark) Downloader")
    print("=" * 70)
    print()
    
    # Step 1: Check git availability
    if not check_git_available():
        print("❌ Git is not available. Please install git first.")
        print("   macOS: brew install git")
        print("   Linux: sudo apt-get install git")
        return 1
    
    # Step 2: Check Kaggle credentials
    print("🔍 Checking Kaggle credentials...")
    cred_path = check_kaggle_credentials()
    if not cred_path:
        print("\n⚠️  Kaggle credentials not found!")
        print("   FDB datasets are downloaded from Kaggle, so credentials are required.")
        print("\n   To set up Kaggle credentials:")
        print("   1. Go to https://www.kaggle.com/settings")
        print("   2. Scroll to 'API' section")
        print("   3. Click 'Create New API Token'")
        print("   4. Download kaggle.json")
        print("   5. Place it at one of these locations:")
        for path in KAGGLE_CREDENTIALS_PATHS:
            print(f"      - {path}")
        print("   6. Set permissions: chmod 600 ~/.kaggle/kaggle.json")
        print("\n   Continuing with repository setup (datasets can be downloaded later)...")
    else:
        print("✅ Kaggle credentials found")
    
    # Step 3: Clone repository
    print(f"\n{'='*70}")
    print("Step 1: Cloning FDB Repository")
    print(f"{'='*70}")
    if not clone_fdb_repository():
        print("\n❌ Failed to clone FDB repository")
        return 1
    
    # Step 4: Install FDB package
    print(f"\n{'='*70}")
    print("Step 2: Installing FDB Package")
    print(f"{'='*70}")
    if not install_fdb_package():
        print("\n❌ Failed to install FDB package")
        return 1
    
    # Step 5: List available datasets
    list_available_datasets()
    
    # Step 6: Ask user if they want to download datasets
    print(f"\n{'='*70}")
    print("Step 3: Download Datasets (Optional)")
    print(f"{'='*70}")
    print("\nWould you like to download datasets now?")
    print("Note: This requires Kaggle credentials and may require joining competitions")
    print("\nOptions:")
    print("  1. Download all datasets")
    print("  2. Download specific dataset(s)")
    print("  3. Skip (download later)")
    
    if cred_path:
        response = input("\nEnter choice (1/2/3) [default: 3]: ").strip() or "3"
        
        if response == "1":
            download_fdb_datasets()
        elif response == "2":
            print("\nAvailable datasets:")
            for i, key in enumerate(FDB_DATASETS, 1):
                print(f"  {i}. {key}")
            selection = input("\nEnter dataset key(s) separated by commas: ").strip()
            selected = [d.strip() for d in selection.split(",") if d.strip() in FDB_DATASETS]
            if selected:
                download_fdb_datasets(selected)
            else:
                print("⚠️  No valid datasets selected")
        else:
            print("\n⏭️  Skipping dataset download")
            print("   You can download datasets later using:")
            print("   ```python")
            print("   from fdb.datasets import FraudDatasetBenchmark")
            print("   obj = FraudDatasetBenchmark(key='ccfraud')")
            print("   train_data = obj.train")
            print("   ```")
    else:
        print("\n⏭️  Skipping dataset download (no Kaggle credentials)")
        print("   Set up Kaggle credentials and run this script again to download datasets")
    
    # Final summary
    print(f"\n{'='*70}")
    print("✅ FDB Setup Complete!")
    print(f"{'='*70}")
    print(f"\n📁 Repository location: {FDB_REPO_DIR}")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("\n💡 Next steps:")
    print("   1. Review FDB documentation in the repository")
    print("   2. Use FDB API to load datasets in your training scripts")
    print("   3. Join required Kaggle competitions if needed")
    print("   4. Download datasets using FDB API")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

