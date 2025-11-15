#!/usr/bin/env python3
"""
Minimal XGBoost training script for SageMaker
Uses XGBoost directly to avoid algorithm mode validation issues
"""

import argparse
import json
import os
import pickle
import gzip

import numpy as np
import xgboost as xgb

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    
    # SageMaker passes hyperparameters as arguments
    parser.add_argument('--objective', type=str, default='binary:logistic')
    parser.add_argument('--num_round', type=int, default=100)
    parser.add_argument('--max_depth', type=int, default=6)
    parser.add_argument('--eta', type=float, default=0.3)
    parser.add_argument('--min_child_weight', type=float, default=1)
    parser.add_argument('--subsample', type=float, default=0.8)
    parser.add_argument('--colsample_bytree', type=float, default=0.8)
    parser.add_argument('--scale_pos_weight', type=float, default=1.0)
    parser.add_argument('--gamma', type=float, default=0.0)
    parser.add_argument('--verbosity', type=int, default=1)
    parser.add_argument('--eval_metric', type=str, default='auc')  # Accept eval_metric as argument
    
    # SageMaker sets these automatically
    parser.add_argument('--model_dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN'))
    parser.add_argument('--validation', type=str, default=os.environ.get('SM_CHANNEL_VALIDATION'))
    
    args = parser.parse_args()
    
    # Determine if files are compressed and find actual file names
    import glob
    
    # Check for compressed files first, then uncompressed
    train_files = glob.glob(f'{args.train}/*.csv.gz') + glob.glob(f'{args.train}/*.csv')
    val_files = glob.glob(f'{args.validation}/*.csv.gz') + glob.glob(f'{args.validation}/*.csv')
    
    if not train_files:
        raise FileNotFoundError(f"No training data found in {args.train}. Files available: {os.listdir(args.train)}")
    if not val_files:
        raise FileNotFoundError(f"No validation data found in {args.validation}. Files available: {os.listdir(args.validation)}")
    
    train_file = train_files[0]
    val_file = val_files[0]
    
    # Determine compression
    train_compression = 'gzip' if train_file.endswith('.gz') else None
    val_compression = 'gzip' if val_file.endswith('.gz') else None
    
    print(f"Loading training data from: {train_file} (compression: {train_compression})")
    print(f"Loading validation data from: {val_file} (compression: {val_compression})")
    
    # Load training data using numpy (avoids pandas/numpy compatibility issues)
    def load_csv_numpy(filepath, compression=None):
        """Load CSV file using numpy, avoiding pandas dependency issues"""
        try:
            if compression == 'gzip':
                # Use genfromtxt for better handling of compressed files
                with gzip.open(filepath, 'rt') as f:
                    data = np.genfromtxt(f, delimiter=',', dtype=np.float32)
            else:
                data = np.genfromtxt(filepath, delimiter=',', dtype=np.float32)
            
            # Remove any NaN rows (shouldn't happen, but just in case)
            data = data[~np.isnan(data).any(axis=1)]
            return data
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            raise
    
    print("Loading training data...")
    train_data = load_csv_numpy(train_file, train_compression)
    X_train = train_data[:, :-1].astype(np.float32)
    y_train = train_data[:, -1].astype(np.float32)
    
    print("Loading validation data...")
    val_data = load_csv_numpy(val_file, val_compression)
    X_val = val_data[:, :-1].astype(np.float32)
    y_val = val_data[:, -1].astype(np.float32)
    
    print(f"Loaded {len(train_data):,} training samples with {X_train.shape[1]} features")
    print(f"Loaded {len(val_data):,} validation samples")
    
    # Create DMatrix
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dval = xgb.DMatrix(X_val, label=y_val)
    
    # Set hyperparameters
    params = {
        'objective': args.objective,
        'max_depth': int(args.max_depth),
        'eta': args.eta,
        'min_child_weight': args.min_child_weight,
        'subsample': args.subsample,
        'colsample_bytree': args.colsample_bytree,
        'scale_pos_weight': args.scale_pos_weight,
        'gamma': args.gamma,
        'eval_metric': args.eval_metric,  # Use argument value
        'verbosity': args.verbosity
    }
    
    # Train model
    evals = [(dtrain, 'train'), (dval, 'validation')]
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=args.num_round,
        evals=evals,
        early_stopping_rounds=10
    )
    
    # Save model
    model.save_model(os.path.join(args.model_dir, 'xgboost-model'))
    
    print('Training complete!')
