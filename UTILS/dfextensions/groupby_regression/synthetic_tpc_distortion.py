#!/usr/bin/env python3
"""
Synthetic TPC Distortion Data Generator
Phase 7 M7.1 - Realistic physical model for validation

Based on § 7.4 Synthetic-Data Test Specification
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional

def make_synthetic_tpc_distortion(
    n_bins_dr: int = 170,      # Radial bins (xBin): 0-170
    n_bins_z2x: int = 20,      # Drift bins (z2xBin): 0-20
    n_bins_y2x: int = 20,      # Sector bins (y2xBin): 0-20
    entries_per_bin: int = 100,
    sigma_meas: float = 0.02,  # Measurement noise (cm)
    seed: int = 42,
    params: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Generate synthetic TPC distortion data with realistic physical model.

    Physical Model:
    ---------------
    dX_true = dX0
              + a_drift * drift * (a1_dr * dr + a2_dr * dr²)
              + a_drift_dsec * drift * (a1_dsec * dsec + a1_dsec_dr * dsec * dr)
              + a1_IDC * meanIDC

    dX_meas = dX_true + N(0, sigma_meas)

    Parameters:
    -----------
    n_bins_dr : int
        Number of radial bins (xBin), typically 170 (1 cm spacing, 82-250 cm)
    n_bins_z2x : int
        Number of drift bins (z2xBin), typically 20 (0=readout, 20=cathode)
    n_bins_y2x : int
        Number of sector coordinate bins (y2xBin), typically 20
    entries_per_bin : int
        Number of tracklet measurements per bin
    sigma_meas : float
        Measurement noise standard deviation (cm)
    seed : int
        Random seed for reproducibility
    params : dict, optional
        Distortion model parameters. If None, uses defaults.

    Returns:
    --------
    pd.DataFrame with columns:
        - xBin: Discrete radial bin index (0-170)
        - y2xBin: Sector coordinate index (0-20)
        - z2xBin: Drift coordinate index (0-20)
        - r: Radius at pad row (cm)
        - dr: Continuous radial coordinate
        - dsec: Relative position to sector centre
        - drift: Drift length along z (cm)
        - meanIDC: Mean current density indicator
        - dX_true: True distortion (cm)
        - dX_meas: Measured distortion with noise (cm)
        - weight: Entry weight (1.0 for now)

    Example:
    --------
    >>> df = make_synthetic_tpc_distortion(entries_per_bin=100)
    >>> # Run sliding window fit
    >>> result = make_sliding_window_fit(
    ...     df, ['xBin', 'y2xBin', 'z2xBin'],
    ...     window_spec={'xBin': 3, 'y2xBin': 2, 'z2xBin': 2},
    ...     fit_columns=['dX_meas'],
    ...     predictor_columns=['drift', 'dr', 'dsec', 'meanIDC'],
    ...     fit_formula='dX_meas ~ drift + dr + I(dr**2) + drift:dsec + ...'
    ... )
    >>> # Check recovery of dX_true
    """

    # Default physical parameters
    if params is None:
        params = {
            'dX0': 0.0,                    # Global offset (cm)
            'a_drift': 1.0e-3,             # Drift scale factor
            'a1_dr': 1.5e-2,               # Linear radial coefficient
            'a2_dr': -4.0e-5,              # Quadratic radial coefficient
            'a_drift_dsec': 5.0e-4,        # Drift-sector coupling
            'a1_dsec': 0.8,                # Sector offset coefficient
            'a1_dsec_dr': 0.3,             # Sector-radial coupling
            'a1_IDC': 2.0e-3               # Mean current sensitivity
        }

    rng = np.random.default_rng(seed)

    # Create 3D grid of bins
    import itertools
    bin_grid = np.array(list(itertools.product(
        range(n_bins_dr),
        range(n_bins_y2x),
        range(n_bins_z2x)
    )))

    # Expand to entries per bin
    bins_expanded = np.repeat(bin_grid, entries_per_bin, axis=0)

    df = pd.DataFrame({
        'xBin': bins_expanded[:, 0].astype(np.int32),
        'y2xBin': bins_expanded[:, 1].astype(np.int32),
        'z2xBin': bins_expanded[:, 2].astype(np.int32)
    })

    # Physical coordinates
    # r: Radius (82-250 cm, corresponding to xBin 0-170)
    df['r'] = 82.0 + df['xBin'] * (250.0 - 82.0) / n_bins_dr

    # dr: Continuous radial coordinate (normalized)
    df['dr'] = df['xBin'].astype(float)

    # drift: Drift length (cm)
    # z2xBin=0 is readout, z2xBin=20 is cathode (~250 cm drift)
    df['drift'] = 250.0 - (df['z2xBin'] / n_bins_z2x) * df['r']

    # dsec: Relative position to sector centre
    # y2xBin=10 is centre, normalized to [-0.5, 0.5]
    df['dsec'] = (df['y2xBin'] - n_bins_y2x/2.0) / n_bins_y2x

    # meanIDC: Mean current density indicator (random per entry)
    df['meanIDC'] = rng.normal(0.0, 1.0, len(df))

    # Weight (uniform for now)
    df['weight'] = 1.0

    # Compute TRUE distortion using physical model
    dX_true = (
        params['dX0']
        + params['a_drift'] * df['drift'] * (
            params['a1_dr'] * df['dr']
            + params['a2_dr'] * df['dr']**2
        )
        + params['a_drift_dsec'] * df['drift'] * (
            params['a1_dsec'] * df['dsec']
            + params['a1_dsec_dr'] * df['dsec'] * df['dr']
        )
        + params['a1_IDC'] * df['meanIDC']
    )

    df['dX_true'] = dX_true

    # Add measurement noise
    df['dX_meas'] = df['dX_true'] + rng.normal(0.0, sigma_meas, len(df))

    # Store ground truth parameters in DataFrame attrs for validation
    df.attrs['ground_truth_params'] = params.copy()
    df.attrs['sigma_meas'] = sigma_meas
    df.attrs['n_bins_dr'] = n_bins_dr
    df.attrs['n_bins_z2x'] = n_bins_z2x
    df.attrs['n_bins_y2x'] = n_bins_y2x
    df.attrs['entries_per_bin'] = entries_per_bin
    df.attrs['seed'] = seed

    return df


def get_ground_truth_params(df: pd.DataFrame) -> Dict[str, float]:
    """Extract ground truth parameters from synthetic DataFrame."""
    return df.attrs.get('ground_truth_params', {})


def get_measurement_noise(df: pd.DataFrame) -> float:
    """Extract measurement noise level from synthetic DataFrame."""
    return df.attrs.get('sigma_meas', 0.02)


if __name__ == '__main__':
    """Test the generator."""
    print("="*70)
    print("Synthetic TPC Distortion Data Generator Test")
    print("="*70)

    # Generate small test dataset
    print("\n📊 Generating test data...")
    df = make_synthetic_tpc_distortion(
        n_bins_dr=170,
        n_bins_z2x=20,
        n_bins_y2x=20,
        entries_per_bin=10,  # Small for test
        seed=42
    )

    print(f"   Generated {len(df):,} rows")
    print(f"   Unique bins: {len(df[['xBin','y2xBin','z2xBin']].drop_duplicates())}")

    print("\n📋 DataFrame columns:")
    for col in df.columns:
        print(f"   - {col}: {df[col].dtype}, range [{df[col].min():.4f}, {df[col].max():.4f}]")

    print("\n📊 Ground truth parameters:")
    params = get_ground_truth_params(df)
    for key, val in params.items():
        print(f"   {key}: {val:.6e}")

    print(f"\n📊 Measurement noise: σ = {get_measurement_noise(df):.4f} cm")

    print("\n📊 Sample statistics:")
    print(f"   dX_true:  μ={df['dX_true'].mean():.6f}, σ={df['dX_true'].std():.6f}")
    print(f"   dX_meas:  μ={df['dX_meas'].mean():.6f}, σ={df['dX_meas'].std():.6f}")
    print(f"   Noise:    RMS={(df['dX_meas']-df['dX_true']).std():.6f} (expected: {get_measurement_noise(df):.4f})")

    print("\n✅ Generator test complete")
