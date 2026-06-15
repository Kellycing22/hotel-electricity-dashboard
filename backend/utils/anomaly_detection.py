import numpy as np
import pandas as pd

def deteksi_anomali(df):
    hasil = {'ada_anomali': False, 'total_anomali': 0, 'jumlah_kritis': 0, 'detail': []}
    cols = ['LWBP_USED', 'WBP_USED', 'A_ELECTRICITY_USED', 'B_ELECTRICITY_USED', 'C_ELECTRICITY_USED']
    for col in cols:
        if col not in df.columns:
            continue
        Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        IQR = Q3 - Q1
        upper = Q3 + 1.5 * IQR
        mask_kritis = (df[col] < 0) | (df[col] > upper * 5)
        n_kritis = mask_kritis.sum()
        if n_kritis > 0:
            hasil['ada_anomali'] = True
            hasil['total_anomali'] += int(n_kritis)
            hasil['jumlah_kritis'] += int(n_kritis)
    return hasil

def bersihkan_anomali_kritis(df):
    cols = ['LWBP_USED', 'WBP_USED', 'A_ELECTRICITY_USED', 'B_ELECTRICITY_USED', 'C_ELECTRICITY_USED']
    n_total = 0
    for col in cols:
        if col not in df.columns:
            continue
        Q1, Q3 = df[col].quantile(0.25), df[col].quantile(0.75)
        IQR = Q3 - Q1
        upper = Q3 + 1.5 * IQR
        mask = (df[col] < 0) | (df[col] > upper * 5)
        n_total += mask.sum()
        df.loc[mask, col] = np.nan
        df[col] = df[col].interpolate(method='linear', limit_direction='both')
    return df, int(n_total)

def format_untuk_dashboard(hasil):
    return hasil