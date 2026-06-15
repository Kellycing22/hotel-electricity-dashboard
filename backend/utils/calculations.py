import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

TARIF_LWBP_KWH = 2400 * 1036 / 1000   # = 2486.4  Rp/kWh
TARIF_WBP_KWH  = 2400 * 1554 / 1000   # = 3729.6  Rp/kWh
TARIF_RESTO    = 1444.7                 # Rp/kWh


# ─────────────────────────────────────────────────────────────
# HITUNG BIAYA DARI SATU BARIS DATA (input dalam kWh)
# ─────────────────────────────────────────────────────────────
def calculate_cost_breakdown(row_or_dict):
    """
    Hitung breakdown biaya dari satu baris data.
    Input  : dict atau pd.Series dengan kolom LWBP_USED_KWH, WBP_USED_KWH, A/B/C_ELECTRICITY_USED
    Output : dict biaya per komponen + total (dalam Rupiah)
    """
    d = row_or_dict

    # Pakai LWBP_USED_KWH (kWh) — hasil konversi preprocessing
    lwbp = float(d.get('LWBP_USED_KWH', 0) or 0)
    wbp  = float(d.get('WBP_USED_KWH',  0) or 0)
    a    = float(d.get('A_ELECTRICITY_USED', 0) or 0)
    b    = float(d.get('B_ELECTRICITY_USED', 0) or 0)
    c    = float(d.get('C_ELECTRICITY_USED', 0) or 0)

    lwbp_cost   = round(lwbp * TARIF_LWBP_KWH, 2)
    wbp_cost    = round(wbp  * TARIF_WBP_KWH,  2)
    area_a_cost = round(a    * TARIF_RESTO,     2)
    area_b_cost = round(b    * TARIF_RESTO,     2)
    area_c_cost = round(c    * TARIF_RESTO,     2)
    total_cost  = round(lwbp_cost + wbp_cost + area_a_cost + area_b_cost + area_c_cost, 2)

    return {
        'lwbp_cost'  : lwbp_cost,
        'wbp_cost'   : wbp_cost,
        'area_a_cost': area_a_cost,
        'area_b_cost': area_b_cost,
        'area_c_cost': area_c_cost,
        'total_cost' : total_cost
    }


# ─────────────────────────────────────────────────────────────
# ESTIMASI BIAYA DARI PREDIKSI kWh TOTAL
# ─────────────────────────────────────────────────────────────
def estimate_cost_from_prediction(predicted_kwh, df_historical):
    """
    Estimasi biaya dari hasil prediksi CNN (TOTAL_PLN_KWH).
    Distribusi komponen dihitung dari rasio historis.
    """
    total_col = 'TOTAL_PLN_KWH'

    # Fallback ke LWBP+WBP jika TOTAL_PLN_KWH belum ada
    if total_col not in df_historical.columns:
        if 'LWBP_USED_KWH' in df_historical.columns and 'WBP_USED_KWH' in df_historical.columns:
            df_historical = df_historical.copy()
            df_historical[total_col] = (df_historical['LWBP_USED_KWH']
                                        + df_historical['WBP_USED_KWH'])
        else:
            return None

    avg_total = df_historical[total_col].mean()
    if avg_total == 0:
        return None

    def ratio(col):
        return df_historical[col].mean() / avg_total if col in df_historical.columns else 0.0

    est_lwbp = predicted_kwh * ratio('LWBP_USED_KWH')
    est_wbp  = predicted_kwh * ratio('WBP_USED_KWH')
    est_a    = predicted_kwh * ratio('A_ELECTRICITY_USED')
    est_b    = predicted_kwh * ratio('B_ELECTRICITY_USED')
    est_c    = predicted_kwh * ratio('C_ELECTRICITY_USED')

    lwbp_cost   = round(est_lwbp * TARIF_LWBP_KWH, 2)
    wbp_cost    = round(est_wbp  * TARIF_WBP_KWH,  2)
    area_a_cost = round(est_a    * TARIF_RESTO,     2)
    area_b_cost = round(est_b    * TARIF_RESTO,     2)
    area_c_cost = round(est_c    * TARIF_RESTO,     2)
    total_cost  = round(lwbp_cost + wbp_cost + area_a_cost + area_b_cost + area_c_cost, 2)

    return {
        'predicted_kwh': round(predicted_kwh, 4),
        'lwbp_cost'    : lwbp_cost,
        'wbp_cost'     : wbp_cost,
        'area_a_cost'  : area_a_cost,
        'area_b_cost'  : area_b_cost,
        'area_c_cost'  : area_c_cost,
        'total_cost'   : total_cost
    }


# ─────────────────────────────────────────────────────────────
# KPI METRICS
# ─────────────────────────────────────────────────────────────
def calculate_metrics(y_true, y_pred):
    y_true = np.array(y_true, dtype=float).flatten()
    y_pred = np.array(y_pred, dtype=float).flatten()
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
    return {
        'MAE' : round(float(mae),  4),
        'RMSE': round(float(rmse), 4),
        'MAPE': round(float(mape), 2)
    }


# ─────────────────────────────────────────────────────────────
# STATISTIK RINGKASAN
# ─────────────────────────────────────────────────────────────
def summarize_data(df):
    """
    Hitung statistik ringkasan dan rata-rata biaya dari df.
    Mendukung kolom kWh (LWBP_USED_KWH) maupun MWh (LWBP_USED) sebagai fallback.
    """
    total_col = 'TOTAL_PLN_KWH'

    # Buat TOTAL_PLN_KWH jika belum ada
    if total_col not in df.columns:
        if 'LWBP_USED_KWH' in df.columns and 'WBP_USED_KWH' in df.columns:
            df = df.copy()
            df[total_col] = df['LWBP_USED_KWH'] + df['WBP_USED_KWH']

    result = {
        'total_records': int(len(df)),
        'avg_daily': None, 'max_daily': None,
        'min_daily': None, 'std_daily': None,
        'zone_a_avg': None, 'zone_b_avg': None, 'zone_c_avg': None,
        'lwbp_avg': None, 'wbp_avg': None,
        'weekend_avg': None, 'weekday_avg': None,
        'avg_total_cost': None, 'avg_lwbp_cost': None, 'avg_wbp_cost': None,
        'avg_area_a_cost': None, 'avg_area_b_cost': None, 'avg_area_c_cost': None,
    }

    # Statistik total harian
    if total_col in df.columns:
        avg = float(df[total_col].mean())
        std = float(df[total_col].std())
        filtered = df[total_col][
            (df[total_col] >= avg - 3 * std) &
            (df[total_col] <= avg + 3 * std)
        ]
        result['avg_daily'] = round(float(filtered.mean()), 4)
        result['max_daily'] = round(float(filtered.max()),  4)
        result['min_daily'] = round(float(filtered.min()),  4)
        result['std_daily'] = round(float(df[total_col].std()), 4)

    # Rata-rata per zona
    for key, col in [('zone_a_avg', 'A_ELECTRICITY_USED'),
                     ('zone_b_avg', 'B_ELECTRICITY_USED'),
                     ('zone_c_avg', 'C_ELECTRICITY_USED')]:
        if col in df.columns:
            result[key] = round(float(df[col].mean()), 4)

    # LWBP dan WBP — pakai kWh (hasil preprocessing)
    if 'LWBP_USED_KWH' in df.columns:
        avg_lwbp            = float(df['LWBP_USED_KWH'].mean())
        result['lwbp_avg']      = round(avg_lwbp, 4)
        result['avg_lwbp_cost'] = round(avg_lwbp * TARIF_LWBP_KWH, 2)

    if 'WBP_USED_KWH' in df.columns:
        avg_wbp            = float(df['WBP_USED_KWH'].mean())
        result['wbp_avg']      = round(avg_wbp, 4)
        result['avg_wbp_cost'] = round(avg_wbp * TARIF_WBP_KWH, 2)

    # Biaya rata-rata zona restoran
    for key, col in [('avg_area_a_cost', 'A_ELECTRICITY_USED'),
                     ('avg_area_b_cost', 'B_ELECTRICITY_USED'),
                     ('avg_area_c_cost', 'C_ELECTRICITY_USED')]:
        if col in df.columns:
            result[key] = round(float(df[col].mean()) * TARIF_RESTO, 2)

    # Total biaya rata-rata
    cost_keys = ['avg_lwbp_cost', 'avg_wbp_cost',
                 'avg_area_a_cost', 'avg_area_b_cost', 'avg_area_c_cost']
    if all(result[k] is not None for k in cost_keys):
        result['avg_total_cost'] = round(sum(result[k] for k in cost_keys), 2)

    # Weekend vs weekday
    if 'IS_WEEKEND' in df.columns and total_col in df.columns:
        wkend = df[df['IS_WEEKEND'] == 1][total_col].mean()
        wkday = df[df['IS_WEEKEND'] == 0][total_col].mean()
        result['weekend_avg'] = round(float(wkend), 4) if not np.isnan(wkend) else None
        result['weekday_avg'] = round(float(wkday), 4) if not np.isnan(wkday) else None

    return result


# ─────────────────────────────────────────────────────────────
# DATA PER ZONA UNTUK CHART
# ─────────────────────────────────────────────────────────────
def zone_breakdown(df):
    result = {'by_zone': {}, 'by_month': {}, 'by_day': {}}

    # Rata-rata per zona
    for zone, col in [('A', 'A_ELECTRICITY_USED'),
                      ('B', 'B_ELECTRICITY_USED'),
                      ('C', 'C_ELECTRICITY_USED')]:
        if col in df.columns:
            result['by_zone'][f'zone_{zone}'] = round(float(df[col].mean()), 4)

    # Tambahkan LWBP dan WBP ke by_zone
    if 'LWBP_USED_KWH' in df.columns:
        result['by_zone']['lwbp'] = round(float(df['LWBP_USED_KWH'].mean()), 4)
    if 'WBP_USED_KWH' in df.columns:
        result['by_zone']['wbp'] = round(float(df['WBP_USED_KWH'].mean()), 4)

    # Per bulan
    total_col = 'TOTAL_PLN_KWH'
    if total_col not in df.columns and 'LWBP_USED_KWH' in df.columns:
        df = df.copy()
        df[total_col] = df['LWBP_USED_KWH'] + df['WBP_USED_KWH']

    if 'MONTH' in df.columns and total_col in df.columns:
        monthly = df.groupby('MONTH')[total_col].mean()
        result['by_month'] = {int(k): round(float(v), 4) for k, v in monthly.items()}

    # Per hari dalam seminggu
    if 'DAY_OF_WEEK' in df.columns and total_col in df.columns:
        daily = df.groupby('DAY_OF_WEEK')[total_col].mean()
        result['by_day'] = {int(k): round(float(v), 4) for k, v in daily.items()}

    return result


# ─────────────────────────────────────────────────────────────
# REKOMENDASI
# ─────────────────────────────────────────────────────────────
def generate_recommendation(prediction_value, avg_historical):
    if avg_historical is None or avg_historical == 0:
        return {'status': 'unknown', 'message': 'Data historis tidak cukup.'}

    ratio = prediction_value / avg_historical

    if ratio > 1.15:
        return {
            'status' : 'high',
            'message': (
                f'Prediksi konsumsi {ratio*100-100:.1f}% di atas rata-rata. '
                'Disarankan: matikan peralatan non-esensial, optimalkan AC, '
                'dan tunda beban berat ke jam LWBP.'
            )
        }
    elif ratio < 0.85:
        return {
            'status' : 'low',
            'message': (
                f'Prediksi konsumsi {100-ratio*100:.1f}% di bawah rata-rata. '
                'Konsumsi energi efisien — pertahankan pola operasional saat ini.'
            )
        }
    else:
        return {
            'status' : 'normal',
            'message': 'Prediksi konsumsi dalam rentang normal. Tidak ada tindakan khusus diperlukan.'
        }