import pandas as pd
import numpy as np

FEATURE_COLS = [
    'DAY_OF_WEEK', 'IS_WEEKEND', 'IS_HOLIDAY', 'WEEK_OF_MONTH', 'MONTH',
    'LWBP_USED_KWH',          # ← kWh (sesuai training NB2)
    'WBP_USED_KWH',           # ← kWh (sesuai training NB2)
    'KVARH_USED',
    'A_ELECTRICITY_USED', 'B_ELECTRICITY_USED', 'C_ELECTRICITY_USED'
]

WINDOW_SIZE = 14


def clean_numeric(value):
    """Bersihkan format angka Indonesia (1.000,50 → 1000.50)"""
    if isinstance(value, str):
        value = value.replace('.', '').replace(',', '.')
    return float(value)


def parse_uploaded_csv(filepath):
    """
    Baca dan bersihkan CSV atau Excel yang diupload user.
    Return: DataFrame yang sudah bersih, atau raise ValueError jika tidak valid.
    """
    filename = str(filepath).lower()

    try:
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else:
            try:
                df = pd.read_csv(filepath, sep=';')
                if df.shape[1] < 5:
                    df = pd.read_csv(filepath, sep=',')
            except Exception:
                df = pd.read_csv(filepath, sep=',')
    except Exception as e:
        raise ValueError(f"Gagal membaca file: {str(e)}")

    # Bersihkan nama kolom
    df.columns = df.columns.str.strip().str.replace(' ', '_')

    # ── Konversi MWh → kWh sebelum cek FEATURE_COLS ─────────────────────────
    # Data mentah dari Excel pakai LWBP_USED (MWh), model butuh LWBP_USED_KWH
    if 'LWBP_USED' in df.columns and 'LWBP_USED_KWH' not in df.columns:
        df['LWBP_USED']    = df['LWBP_USED'].apply(clean_numeric)
        df['LWBP_USED_KWH'] = df['LWBP_USED'] * 1000

    if 'WBP_USED' in df.columns and 'WBP_USED_KWH' not in df.columns:
        df['WBP_USED']    = df['WBP_USED'].apply(clean_numeric)
        df['WBP_USED_KWH'] = df['WBP_USED'] * 1000

    # ── Buat TOTAL_PLN_KWH ───────────────────────────────────────────────────
    if 'LWBP_USED_KWH' in df.columns and 'WBP_USED_KWH' in df.columns:
        df['TOTAL_PLN_KWH'] = df['LWBP_USED_KWH'] + df['WBP_USED_KWH']

    # ── Cek kolom yang diperlukan ─────────────────────────────────────────────
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom tidak ditemukan di file: {missing}")

    # ── Konversi numerik semua feature ───────────────────────────────────────
    for col in FEATURE_COLS:
        df[col] = df[col].apply(clean_numeric)

    extra_numeric = [
        'TOTAL_PLN_KWH', 'TOTAL_BUILDING_ELECTRICITY', 'TOTAL_PRICE',
        'LWBP_PRICE', 'WBP_PRICE',
        'A_ELECTRICITY_PRICE', 'B_ELECTRICITY_PRICE', 'C_ELECTRICITY_PRICE',
    ]
    for col in extra_numeric:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

    # ── Konversi DATE ─────────────────────────────────────────────────────────
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce')
        df = df.sort_values('DATE').reset_index(drop=True)

    # ── Cek jumlah data minimal ───────────────────────────────────────────────
    if len(df) < WINDOW_SIZE:
        raise ValueError(
            f"Data minimal {WINDOW_SIZE} baris, hanya ada {len(df)} baris."
        )

    # ── Log ringkasan ─────────────────────────────────────────────────────────
    print(f"[preprocessing] ✅ {len(df)} baris siap diproses")
    print(f"[preprocessing]    LWBP_USED_KWH mean : {df['LWBP_USED_KWH'].mean():.2f} kWh")
    print(f"[preprocessing]    WBP_USED_KWH  mean : {df['WBP_USED_KWH'].mean():.2f} kWh")
    if 'TOTAL_PLN_KWH' in df.columns:
        print(f"[preprocessing]    TOTAL_PLN_KWH mean : {df['TOTAL_PLN_KWH'].mean():.2f} kWh")

    return df


def build_sequences(df, scaler_X):
    """
    Buat sliding window sequences dari DataFrame.
    Return: np.array shape (n_samples, WINDOW_SIZE, n_features)
    """
    X        = df[FEATURE_COLS].values
    X_scaled = scaler_X.transform(X)

    sequences = []
    for i in range(WINDOW_SIZE, len(X_scaled)):
        sequences.append(X_scaled[i - WINDOW_SIZE:i])

    # Fallback: jika data pas 14 baris, pakai seluruhnya sebagai 1 window
    if len(sequences) == 0:
        sequences.append(X_scaled[-WINDOW_SIZE:])

    return np.array(sequences)


def build_single_sequence(df, scaler_X):
    """
    Buat 1 sequence dari 14 baris terakhir untuk prediksi 1 hari ke depan.
    Return: np.array shape (1, WINDOW_SIZE, n_features)
    """
    if len(df) < WINDOW_SIZE:
        raise ValueError(f"Butuh minimal {WINDOW_SIZE} baris data.")

    X        = df[FEATURE_COLS].tail(WINDOW_SIZE).values
    X_scaled = scaler_X.transform(X)
    return X_scaled.reshape(1, WINDOW_SIZE, len(FEATURE_COLS))