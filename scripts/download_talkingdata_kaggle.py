#!/usr/bin/env python3
"""
Download TalkingData AdTracking Fraud Detection dataset from Kaggle
https://www.kaggle.com/competitions/talkingdata-adtracking-fraud-detection

This dataset contains mobile app ad clicks with fraud labels, which is highly
relevant for ad fraud detection training.
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess

# Try to import Kaggle API
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    KAGGLE_API_AVAILABLE = True
except ImportError:
    KAGGLE_API_AVAILABLE = False

# Configuration
KAGGLE_COMPETITION = "talkingdata-adtracking-fraud-detection"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "talkingdata"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Kaggle credentials path
KAGGLE_CREDENTIALS_PATHS = [
    Path.home() / ".kaggle" / "kaggle.json",
    Path(__file__).parent.parent / "kaggle" / "kaggle.json",
]


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


def check_kaggle_api() -> bool:
    """
    Check if Kaggle API is available
    """
    if KAGGLE_API_AVAILABLE:
        print("✅ Kaggle Python API is available")
        return True
    else:
        print("❌ Kaggle Python API not found")
        return False


def install_kaggle() -> bool:
    """
    Attempt to install Kaggle package
    """
    print("📦 Attempting to install Kaggle package...")
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'kaggle', '--upgrade', '--user'],
            check=True,
            timeout=60
        )
        print("✅ Kaggle package installed successfully")
        # Reload the module
        global KAGGLE_API_AVAILABLE
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            KAGGLE_API_AVAILABLE = True
            return True
        except ImportError:
            print("⚠️  Package installed but import failed. Please restart Python.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Kaggle: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error installing Kaggle: {str(e)}")
        return False


def download_dataset() -> bool:
    """
    Download the TalkingData dataset using Kaggle API
    """
    if not KAGGLE_API_AVAILABLE:
        print("❌ Kaggle API not available")
        return False
    
    try:
        print(f"\n📥 Downloading {KAGGLE_COMPETITION} dataset...")
        print(f"   Output directory: {OUTPUT_DIR}")
        
        # Initialize Kaggle API
        api = KaggleApi()
        api.authenticate()
        print("✅ Authenticated with Kaggle API")
        
        # Download competition files
        # Note: This requires accepting competition rules on Kaggle first
        print(f"\n📦 Downloading competition files...")
        print("   (This may take a while for large datasets)")
        
        # Download files (they come as zip files)
        api.competition_download_files(
            KAGGLE_COMPETITION,
            path=str(OUTPUT_DIR)
        )
        
        print("✅ Files downloaded successfully!")
        
        # Unzip downloaded files
        print("\n📦 Extracting downloaded files...")
        import zipfile
        zip_files = list(OUTPUT_DIR.glob("*.zip"))
        for zip_file in zip_files:
            print(f"   Extracting {zip_file.name}...")
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(OUTPUT_DIR)
            print(f"   ✅ Extracted {zip_file.name}")
            # Optionally remove zip file after extraction
            # zip_file.unlink()
        
        print("\n✅ Dataset downloaded and extracted successfully!")
        return True
            
    except Exception as e:
        error_str = str(e)
        print(f"❌ Error downloading dataset: {error_str}")
        
        # Check for common errors
        if "403" in error_str or "Forbidden" in error_str:
            print("\n⚠️  Error: 403 Forbidden")
            print("   This usually means:")
            print("   1. You need to accept the competition rules on Kaggle")
            print(f"   2. Visit: https://www.kaggle.com/competitions/{KAGGLE_COMPETITION}")
            print("   3. Click 'Join Competition' and accept the rules")
            print("   4. Then run this script again")
        elif "401" in error_str or "Unauthorized" in error_str:
            print("\n⚠️  Error: 401 Unauthorized")
            print("   Please check your Kaggle credentials:")
            print("   1. Download kaggle.json from https://www.kaggle.com/settings")
            print("   2. Place it at ~/.kaggle/kaggle.json")
            print("   3. Set permissions: chmod 600 ~/.kaggle/kaggle.json")
        elif "404" in error_str or "Not Found" in error_str:
            print("\n⚠️  Error: Competition not found")
            print(f"   Please verify the competition name: {KAGGLE_COMPETITION}")
            print(f"   URL: https://www.kaggle.com/competitions/{KAGGLE_COMPETITION}")
        
        return False


def list_downloaded_files() -> None:
    """
    List downloaded files
    """
    print("\n📁 Downloaded files:")
    files = list(OUTPUT_DIR.glob("*"))
    if files:
        for f in sorted(files):
            size_mb = f.stat().st_size / (1024 * 1024) if f.is_file() else 0
            file_type = "📄" if f.is_file() else "📁"
            print(f"   {file_type} {f.name} ({size_mb:.2f} MB)" if f.is_file() else f"   {file_type} {f.name}/")
    else:
        print("   No files found")


def create_dataset_info() -> None:
    """
    Create a dataset info file with metadata
    """
    info = {
        "dataset_name": "TalkingData AdTracking Fraud Detection",
        "source": "Kaggle",
        "competition_url": f"https://www.kaggle.com/competitions/{KAGGLE_COMPETITION}",
        "description": "Mobile app ad clicks dataset with fraud labels",
        "features": [
            "IP address",
            "App ID",
            "Device ID",
            "OS version",
            "Channel ID",
            "Click timestamp",
            "Is attributed (fraud label)"
        ],
        "use_cases": [
            "Train XGBoost fraud detection model",
            "Feature engineering for ad fraud",
            "Benchmarking fraud detection algorithms"
        ],
        "notes": [
            "Requires accepting competition rules on Kaggle",
            "Large dataset - may take time to download",
            "Contains millions of mobile ad click records"
        ]
    }
    
    info_path = OUTPUT_DIR / "dataset_info.json"
    with open(info_path, 'w') as f:
        json.dump(info, f, indent=2)
    
    print(f"\n✅ Created dataset info: {info_path}")


def main():
    """
    Main function to download TalkingData dataset
    """
    print("=" * 70)
    print("TalkingData AdTracking Fraud Detection Dataset Downloader")
    print("=" * 70)
    print()
    
    # Step 1: Check Kaggle API
    if not check_kaggle_api():
        print("\n📦 Kaggle package not found. Installing...")
        if not install_kaggle():
            print("\n❌ Please install Kaggle package manually:")
            print("   pip install kaggle")
            return 1
        if not check_kaggle_api():
            return 1
    
    # Step 2: Check credentials
    cred_path = check_kaggle_credentials()
    if not cred_path:
        print("\n❌ Kaggle credentials not found!")
        print("\nPlease set up Kaggle credentials:")
        print("1. Go to https://www.kaggle.com/settings")
        print("2. Scroll to 'API' section")
        print("3. Click 'Create New API Token'")
        print("4. Download kaggle.json")
        print("5. Place it at one of these locations:")
        for path in KAGGLE_CREDENTIALS_PATHS:
            print(f"   - {path}")
        print("6. Set permissions: chmod 600 ~/.kaggle/kaggle.json")
        return 1
    
    # Step 3: Download dataset
    print(f"\n{'='*70}")
    print("Downloading Dataset")
    print(f"{'='*70}")
    
    if download_dataset():
        list_downloaded_files()
        create_dataset_info()
        print("\n✅ Successfully downloaded TalkingData dataset!")
        print(f"\n📊 Dataset location: {OUTPUT_DIR}")
        print("\n💡 Next steps:")
        print("   1. Review the downloaded files")
        print("   2. Integrate into training pipeline")
        print("   3. Use for XGBoost model training")
        return 0
    else:
        print("\n❌ Failed to download dataset")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure you've accepted competition rules on Kaggle")
        print(f"   2. Visit: https://www.kaggle.com/competitions/{KAGGLE_COMPETITION}")
        print("   3. Click 'Join Competition' if you haven't already")
        return 1


if __name__ == '__main__':
    sys.exit(main())

