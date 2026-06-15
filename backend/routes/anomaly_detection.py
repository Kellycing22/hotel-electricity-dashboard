"""
anomaly_detection.py
====================
Modul deteksi anomali konsumsi energi hotel.
Dipanggil di preprocessing.py SEBELUM data masuk ke model CNN.

Referensi: Loureiro et al. (2023), Applied Sciences, 13(1), 314.
           DOI: 10.3390/app13010314
"""

import pandas as pd
import numpy as np


# Kolom yang dicek anomalinya beserta label tampilan
KOLOM_CEK = {
    'TOTAL_BUILDING_ELECTRICITY': 'Gedung Utama',
    'A_ELECTRICITY_USED':         'Zona A (Resto A)',
    'B_ELECTRICITY_USED':         'Zona B (Resto B)',
    'C_ELECTRICITY_USED':         'Zona C (Resto C)',
    'LWBP_USED':                  'LWBP',
    'WBP_USED':                   'WBP',
}


def hitung_batas_iqr(series, multiplier=1.5):
    """
    Hitung batas bawah dan atas menggunakan metode IQR.
    Referensi: Loureiro et al. (2023) — sliding window anomaly detection.
    """
    Q1 = series.quantile(0.25)
    Q3 = series.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - multiplier * IQR
    upper = Q3 + multiplier * IQR
    return round(lower, 2), round(upper, 2)


def deteksi_anomali(df: pd.DataFrame) -> dict:
    """
    Deteksi anomali pada DataFrame konsumsi energi hotel.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset yang sudah di-load dari Excel/CSV.
        Harus memiliki kolom DATE dan kolom-kolom di KOLOM_CEK.

    Returns
    -------
    dict dengan keys:
        - 'anomali'      : DataFrame daftar baris anomali + keterangan
        - 'ringkasan'    : dict ringkasan per zona
        - 'kritis'       : DataFrame anomali kritis (>5x batas atau negatif)
        - 'total'        : jumlah total anomali
        - 'persen'       : persentase baris anomali dari total data
    """
    df = df.copy()
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE'])

    hasil = []
    ringkasan = {}

    for col, label in KOLOM_CEK.items():
        if col not in df.columns:
            continue

        lower, upper = hitung_batas_iqr(df[col])
        anomali_mask = (df[col] < lower) | (df[col] > upper)
        anomali_df = df[anomali_mask]

        ringkasan[label] = {
            'total_anomali': int(anomali_mask.sum()),
            'terlalu_tinggi': int((df[col] > upper).sum()),
            'terlalu_rendah': int((df[col] < lower).sum()),
            'batas_min': lower,
            'batas_max': upper,
            'nilai_median': round(df[col].median(), 2),
        }

        for _, row in anomali_df.iterrows():
            nilai = row[col]
            flag = 'TERLALU TINGGI' if nilai > upper else 'TERLALU RENDAH'
            # Tandai sebagai kritis jika >5x batas atas atau negatif
            is_kritis = (nilai > upper * 5) or (nilai < 0)

            hasil.append({
                'Tanggal':        row['DATE'].date() if 'DATE' in df.columns else '-',
                'Zona':           label,
                'Nilai (kWh)':    round(nilai, 2),
                'Batas Min':      lower,
                'Batas Max':      upper,
                'Status':         flag,
                'Kritis':         'YA' if is_kritis else 'tidak',
            })

    df_anomali = pd.DataFrame(hasil)
    if not df_anomali.empty and 'Tanggal' in df_anomali.columns:
        df_anomali = df_anomali.sort_values('Tanggal').reset_index(drop=True)

    df_kritis = df_anomali[df_anomali['Kritis'] == 'YA'] if not df_anomali.empty else pd.DataFrame()
    total = len(df_anomali)
    persen = round(total / len(df) * 100, 2) if len(df) > 0 else 0

    return {
        'anomali':   df_anomali,
        'ringkasan': ringkasan,
        'kritis':    df_kritis,
        'total':     total,
        'persen':    persen,
    }


def bersihkan_anomali_kritis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hapus baris dengan anomali KRITIS (nilai >5x batas atas atau negatif)
    dan ganti dengan NaN, lalu imputasi dengan interpolasi linear.

    Ini adalah langkah data cleaning SEBELUM masuk CNN.
    Anomali non-kritis (sedikit di luar batas) DIBIARKAN — bisa jadi
    kondisi operasional nyata seperti event besar atau renovasi.

    Returns
    -------
    df_bersih : DataFrame yang sudah dibersihkan
    n_dibersihkan : jumlah nilai yang diimputasi
    """
    df = df.copy()
    n_dibersihkan = 0

    for col in KOLOM_CEK.keys():
        if col not in df.columns:
            continue
        lower, upper = hitung_batas_iqr(df[col])
        mask_kritis = (df[col] > upper * 5) | (df[col] < 0)
        n_kritis = mask_kritis.sum()
        if n_kritis > 0:
            df.loc[mask_kritis, col] = np.nan
            df[col] = df[col].interpolate(method='linear', limit_direction='both')
            n_dibersihkan += n_kritis

    return df, n_dibersihkan


def format_untuk_dashboard(hasil: dict) -> dict:
    """
    Format hasil deteksi anomali untuk ditampilkan di dashboard Flask.

    Returns dict yang bisa langsung di-pass ke template Jinja2.
    """
    return {
        'total_anomali':     hasil['total'],
        'persen_anomali':    hasil['persen'],
        'jumlah_kritis':     len(hasil['kritis']),
        'tabel_anomali':     hasil['anomali'].to_dict('records'),
        'tabel_kritis':      hasil['kritis'].to_dict('records'),
        'ringkasan_zona':    hasil['ringkasan'],
        'ada_anomali':       hasil['total'] > 0,
        'ada_kritis':        len(hasil['kritis']) > 0,
    }


# ============================================================
# Contoh penggunaan di preprocessing.py Flask:
# ============================================================
#
# from anomaly_detection import deteksi_anomali, bersihkan_anomali_kritis, format_untuk_dashboard
#
# @app.route('/upload', methods=['POST'])
# def upload():
#     file = request.files['file']
#     df = pd.read_excel(file)
#
#     # 1. Deteksi anomali SEBELUM cleaning
#     hasil = deteksi_anomali(df)
#     data_dashboard = format_untuk_dashboard(hasil)
#
#     # 2. Bersihkan anomali kritis saja
#     df_bersih, n_fixed = bersihkan_anomali_kritis(df)
#
#     # 3. Lanjut ke preprocessing CNN seperti biasa
#     # ... normalisasi, sliding window, predict ...
#
#     return render_template('hasil.html',
#                            anomali=data_dashboard,
#                            n_fixed=n_fixed)
