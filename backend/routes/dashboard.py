from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from routes.auth import token_required
from utils.database import (
    get_latest_records,
    get_records_by_date_range,
    get_records_by_month,
    get_records_by_year,
    get_monthly_summary
)
import numpy as np
import os
import joblib

dashboard_bp = Blueprint('dashboard', __name__)

# ============================================================
# KONSTANTA TARIF DAN PROPORSI GSO
# ============================================================
TARIF_LWBP  = 2486.4   # Rp/kWh
TARIF_WBP   = 3729.6   # Rp/kWh
TARIF_RESTO = 1444.7   # Rp/kWh

TOTAL_HIST = 1959 + 445 + 515 + 156 + 108  # = 3183 kWh
PROP = {
    'lwbp': 1959 / TOTAL_HIST,
    'wbp':  445  / TOTAL_HIST,
    'a':    515  / TOTAL_HIST,
    'b':    156  / TOTAL_HIST,
    'c':    108  / TOTAL_HIST,
}

# ============================================================
# FEATURE COLS (harus sama persis dengan training NB2)
# ============================================================
FEATURE_COLS = [
    'day_of_week', 'is_weekend', 'is_holiday', 'week_of_month', 'month',
    'lwbp_used_kwh', 'wbp_used_kwh', 'kvarh_used',
    'a_electricity_used', 'b_electricity_used', 'c_electricity_used'
]

WINDOW_SIZE = 14

# ============================================================
# LOAD SCALER DAN MODEL (cached)
# ============================================================
_model_utama  = None
_scaler_X     = None
_scaler_y     = None

def _get_model_and_scalers():
    global _model_utama, _scaler_X, _scaler_y

    if _model_utama is None:
        try:
            import tensorflow as tf
            for path in ['models/model_gedung_utama.h5',
                         'models/model_gedung_utama.keras']:
                if os.path.exists(path):
                    _model_utama = tf.keras.models.load_model(path, compile=False)
                    print(f'[dashboard] ✅ Model loaded: {path}')
                    break
        except Exception as e:
            print(f'[dashboard] Model load error: {e}')

    if _scaler_X is None:
        path = 'models/scaler_X.pkl'
        if os.path.exists(path):
            _scaler_X = joblib.load(path)
            print('[dashboard] ✅ scaler_X loaded')

    if _scaler_y is None:
        path = 'models/scaler_y_gedung_utama.pkl'
        if os.path.exists(path):
            _scaler_y = joblib.load(path)
            print(f'[dashboard] ✅ scaler_y loaded '
                  f'(min={float(_scaler_y.data_min_[0]):.2f}, '
                  f'max={float(_scaler_y.data_max_[0]):.2f})')

    return _model_utama, _scaler_X, _scaler_y


# ============================================================
# HELPER: BUAT FEATURE ROW DARI SATU RECORD DB
# ============================================================
def _record_to_feature_row(r):
    """
    Konversi 1 record database ke feature row untuk CNN.
    LWBP_USED dan WBP_USED dari DB dalam MWh → konversi ke kWh.
    """
    d = r['record_date']
    return [
        d.weekday() + 1,                              # day_of_week (1=Senin)
        1 if d.weekday() >= 5 else 0,                  # is_weekend
        int(r.get('is_holiday', 0) or 0),              # is_holiday
        (d.day - 1) // 7 + 1,                          # week_of_month
        d.month,                                        # month
        float(r.get('lwbp_used', 0) or 0) * 1000,     # lwbp_used_kwh (MWh→kWh)
        float(r.get('wbp_used',  0) or 0) * 1000,     # wbp_used_kwh  (MWh→kWh)
        float(r.get('kvarh_used', 0) or 0),            # kvarh_used
        float(r.get('a_electricity_used', 0) or 0),    # a
        float(r.get('b_electricity_used', 0) or 0),    # b
        float(r.get('c_electricity_used', 0) or 0),    # c
    ]


def _get_total_pln_kwh(record):
    """Hitung TOTAL_PLN_KWH dari satu record (LWBP+WBP dalam kWh)."""
    lwbp_kwh = float(record.get('lwbp_used', 0) or 0) * 1000
    wbp_kwh  = float(record.get('wbp_used',  0) or 0) * 1000
    return lwbp_kwh + wbp_kwh


# ============================================================
# HELPER: PREDIKSI CNN
# ============================================================
def prediksi_cnn(records_14_hari):
    """
    Prediksi 1 hari ke depan menggunakan CNN + scaler training.
    Input : 14 record terakhir dari database
    Output: float (kWh prediksi TOTAL_PLN_KWH)
    """
    # Fallback value (mean TOTAL_PLN_KWH dari 14 hari)
    vals_fallback = [_get_total_pln_kwh(r) for r in records_14_hari]
    fallback      = round(sum(vals_fallback) / len(vals_fallback), 2) if vals_fallback else 2404.42

    try:
        model, scaler_X, scaler_y = _get_model_and_scalers()

        if model is None or scaler_X is None or scaler_y is None:
            print('[dashboard] prediksi_cnn: model/scaler tidak tersedia, pakai fallback')
            return fallback

        if len(records_14_hari) < WINDOW_SIZE:
            return fallback

        # Buat feature matrix dari 14 record
        X = np.array([_record_to_feature_row(r) for r in records_14_hari[-WINDOW_SIZE:]])

        # Normalisasi dengan scaler training (bukan fit ulang!)
        X_scaled = scaler_X.transform(X)
        X_seq    = X_scaled.reshape(1, WINDOW_SIZE, len(FEATURE_COLS))

        pred_scaled = float(model.predict(X_seq, verbose=0)[0][0])

        # Inverse transform dengan scaler_y training
        pred_kwh = float(scaler_y.inverse_transform([[pred_scaled]])[0][0])

        print(f'[dashboard] pred_scaled={pred_scaled:.4f} → pred={pred_kwh:.2f} kWh')
        return round(pred_kwh, 2)

    except Exception as e:
        print(f'[dashboard] prediksi_cnn error: {e}')
        return fallback


# ============================================================
# HELPER: ALOKASI GSO (1-dimensi, untuk dashboard)
# ============================================================
def hitung_alokasi_gso(E_pred, n_points=100):
    """
    GSO 1-dimensi: cari split LWBP optimal untuk dashboard.
    Resto A/B/C proporsi fixed dari rata-rata historis.
    """
    prop_resto = PROP['a'] + PROP['b'] + PROP['c']
    E_resto    = E_pred * prop_resto
    E_gedung   = E_pred * (1 - prop_resto)

    lb = E_gedung * 0.60
    ub = E_gedung * 0.95

    best_cost = float('inf')
    best_lwbp = lb

    for i in range(n_points + 1):
        x_lwbp = lb + (ub - lb) * i / n_points
        x_wbp  = E_gedung - x_lwbp
        cost   = x_lwbp * TARIF_LWBP + x_wbp * TARIF_WBP + E_resto * TARIF_RESTO
        if cost < best_cost:
            best_cost = cost
            best_lwbp = x_lwbp

    x_wbp = E_gedung - best_lwbp
    x_a   = E_resto * (PROP['a'] / prop_resto)
    x_b   = E_resto * (PROP['b'] / prop_resto)
    x_c   = E_resto * (PROP['c'] / prop_resto)

    return {
        'lwbp_kwh':      round(best_lwbp, 2),
        'wbp_kwh':       round(x_wbp,    2),
        'resto_a_kwh':   round(x_a,       2),
        'resto_b_kwh':   round(x_b,       2),
        'resto_c_kwh':   round(x_c,       2),
        'biaya_optimal': round(best_cost, 0),
    }


# ============================================================
# FORECAST 10 HARI
# ============================================================
@dashboard_bp.route('/forecast', methods=['GET'])
@token_required
def get_forecast(current_user):
    try:
        records_14 = get_latest_records(14)
        if not records_14:
            return jsonify({'success': False, 'error': 'Tidak ada data historis'}), 404

        # Rata-rata biaya aktual dari 14 hari terakhir
        avg_biaya_aktual = sum(
            float(r.get('total_price', 0) or 0) for r in records_14
        ) / len(records_14)

        base_pred = prediksi_cnn(records_14)

        hari_variasi = {0: +2, 1: +1, 2: 0, 3: -1, 4: +3, 5: +5, 6: +4}

        today    = datetime.now().date()
        forecast = []

        for i in range(10):
            tgl          = today + timedelta(days=i)
            dow          = tgl.weekday()
            variasi_pct  = hari_variasi.get(dow, 0) / 100
            pred_kwh     = round(base_pred * (1 + variasi_pct), 2)
            alokasi      = hitung_alokasi_gso(pred_kwh)

            penghematan = 0
            if avg_biaya_aktual > 0:
                penghematan = round(
                    (avg_biaya_aktual - alokasi['biaya_optimal']) / avg_biaya_aktual * 100, 2
                )

            if pred_kwh > base_pred * 1.05:
                status = 'tinggi'
            elif pred_kwh < base_pred * 0.97:
                status = 'hemat'
            else:
                status = 'normal'

            forecast.append({
                'tanggal':          tgl.strftime('%Y-%m-%d'),
                'hari':             tgl.strftime('%A'),
                'prediksi_kwh':     pred_kwh,
                'alokasi':          alokasi,
                'biaya_aktual_ref': round(avg_biaya_aktual, 0),
                'penghematan_pct':  penghematan,
                'status':           status,
            })

        rata_pred  = round(sum(f['prediksi_kwh'] for f in forecast) / 10, 2)
        rata_biaya = round(sum(f['alokasi']['biaya_optimal'] for f in forecast) / 10, 0)
        rata_hemat = round(sum(f['penghematan_pct'] for f in forecast) / 10, 2)

        return jsonify({
            'success':  True,
            'forecast': forecast,
            'ringkasan': {
                'rata_prediksi_kwh':    rata_pred,
                'rata_biaya_optimal':   rata_biaya,
                'rata_penghematan_pct': rata_hemat,
                'model_used':           'CNN-GSO',
                'mape_gedung':          9.23,   # ← diupdate dari hasil terbaru
            }
        }), 200

    except Exception as e:
        print(f'[dashboard] Forecast error: {e}')
        return jsonify({'success': False, 'error': 'Gagal menghitung forecast'}), 500


# ============================================================
# TODAY VIEW
# ============================================================
@dashboard_bp.route('/today', methods=['GET'])
@token_required
def get_today_data(current_user):
    try:
        date_str = request.args.get('date')

        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            records = get_records_by_date_range(target_date, target_date)
        else:
            records = get_latest_records(1)

        if not records:
            return jsonify({'success': False, 'error': 'No data found'}), 404

        today_record = records[0]
        target_date  = today_record['record_date']

        lwbp_cost   = float(today_record['lwbp_price'])
        wbp_cost    = float(today_record['wbp_price'])
        area_a_cost = float(today_record['a_electricity_price'])
        area_b_cost = float(today_record['b_electricity_price'])
        area_c_cost = float(today_record['c_electricity_price'])
        total_cost  = lwbp_cost + wbp_cost + area_a_cost + area_b_cost + area_c_cost

        # Gunakan TOTAL_PLN_KWH (LWBP+WBP dalam kWh) bukan total_building_electricity
        total_pln_kwh = _get_total_pln_kwh(today_record)
        lwbp_kwh      = float(today_record.get('lwbp_used', 0) or 0) * 1000
        wbp_kwh       = float(today_record.get('wbp_used',  0) or 0) * 1000

        actual_data = {
            'total_cost':       total_cost,
            'lwbp_cost':        lwbp_cost,
            'wbp_cost':         wbp_cost,
            'area_a_cost':      area_a_cost,
            'area_b_cost':      area_b_cost,
            'area_c_cost':      area_c_cost,
            'lwbp_used_kwh':    round(lwbp_kwh, 2),
            'wbp_used_kwh':     round(wbp_kwh,  2),
            'lwbp_percentage':  round(lwbp_cost / total_cost * 100, 1) if total_cost > 0 else 0,
            'wbp_percentage':   round(wbp_cost  / total_cost * 100, 1) if total_cost > 0 else 0,
            'total_usage':      round(total_pln_kwh, 2),   # ← TOTAL_PLN_KWH
            'area_a':           float(today_record['a_electricity_used']),
            'area_b':           float(today_record['b_electricity_used']),
            'area_c':           float(today_record['c_electricity_used']),
        }

        alokasi_gso = hitung_alokasi_gso(actual_data['total_usage'])
        penghematan = 0
        if total_cost > 0:
            penghematan = round(
                (total_cost - alokasi_gso['biaya_optimal']) / total_cost * 100, 2
            )

        records_14    = get_latest_records(14)
        next_day_pred = prediksi_cnn(records_14)
        next_day_alloc = hitung_alokasi_gso(next_day_pred)
        tomorrow_date  = target_date + timedelta(days=1)

        yesterday_date    = target_date - timedelta(days=1)
        yesterday_records = get_records_by_date_range(yesterday_date, yesterday_date)
        yesterday_cost    = 0
        cost_change_pct   = 0

        if yesterday_records:
            y = yesterday_records[0]
            yesterday_cost = (
                float(y['lwbp_price']) + float(y['wbp_price']) +
                float(y['a_electricity_price']) + float(y['b_electricity_price']) +
                float(y['c_electricity_price'])
            )
            if yesterday_cost > 0:
                cost_change_pct = round(
                    (total_cost - yesterday_cost) / yesterday_cost * 100, 2
                )

        actual_data['cost_change_percent'] = cost_change_pct
        actual_data['yesterday_cost']      = yesterday_cost

        return jsonify({
            'success': True,
            'mode':    'today',
            'date':    target_date.strftime('%Y-%m-%d'),
            'actual':  actual_data,
            'alokasi_gso': {
                **alokasi_gso,
                'penghematan_pct': penghematan,
            },
            'prediction': {
                'tomorrow_date':  tomorrow_date.strftime('%Y-%m-%d'),
                'predicted_kwh':  next_day_pred,
                'alokasi':        next_day_alloc,
                'estimated_cost': next_day_alloc['biaya_optimal'],
            }
        }), 200

    except Exception as e:
        print(f'[dashboard] Today data error: {e}')
        return jsonify({'success': False, 'error': 'Failed to fetch today data'}), 500


# ============================================================
# MONTH VIEW
# ============================================================
@dashboard_bp.route('/month', methods=['GET'])
@token_required
def get_month_data(current_user):
    try:
        month = request.args.get('month')
        year  = request.args.get('year')

        if month and year:
            month, year = int(month), int(year)
        else:
            latest = get_latest_records(1)
            if latest:
                latest_date = latest[0]['record_date']
                month, year = latest_date.month, latest_date.year
            else:
                month, year = datetime.now().month, datetime.now().year

        if month < 1 or month > 12:
            return jsonify({'success': False, 'error': 'Invalid month'}), 400

        records = get_records_by_month(month, year)
        if not records:
            return jsonify({'success': False, 'error': 'No data found for this month'}), 404

        actual_days  = len(records)
        actual_cost  = sum(float(r['total_price']) for r in records)

        # Gunakan TOTAL_PLN_KWH untuk semua kalkulasi usage
        actual_usage = sum(_get_total_pln_kwh(r) for r in records)
        avg_daily    = actual_usage / actual_days if actual_days > 0 else 0

        if month == 12:
            next_month_dt = datetime(year + 1, 1, 1)
        else:
            next_month_dt = datetime(year, month + 1, 1)
        last_day       = (next_month_dt - timedelta(days=1)).day
        remaining_days = last_day - actual_days

        predicted_usage = avg_daily * remaining_days
        predicted_cost  = (actual_cost / actual_usage * avg_daily * remaining_days) if actual_usage > 0 else 0

        prev_month   = month - 1 if month > 1 else 12
        prev_year    = year if month > 1 else year - 1
        prev_records = get_records_by_month(prev_month, prev_year)
        prev_cost    = sum(float(r['total_price']) for r in prev_records) if prev_records else 0

        total_month_cost = actual_cost + predicted_cost
        change_amount    = total_month_cost - prev_cost
        change_pct       = (change_amount / prev_cost * 100) if prev_cost > 0 else 0

        avg_biaya_aktual = actual_cost / actual_days if actual_days > 0 else 0
        avg_alokasi      = hitung_alokasi_gso(avg_daily)
        penghematan_pct  = round(
            (avg_biaya_aktual - avg_alokasi['biaya_optimal']) / avg_biaya_aktual * 100, 2
        ) if avg_biaya_aktual > 0 else 13.70

        daily_data = []
        for r in records:
            daily_data.append({
                'date':      r['record_date'].strftime('%Y-%m-%d'),
                'actual':    round(_get_total_pln_kwh(r), 2),   # ← TOTAL_PLN_KWH
                'cost':      float(r['total_price']),
                'predicted': None,
            })
        for i in range(1, remaining_days + 1):
            pred_date = datetime(year, month, actual_days + i)
            daily_data.append({
                'date':      pred_date.strftime('%Y-%m-%d'),
                'actual':    None,
                'cost':      None,
                'predicted': round(avg_daily, 2),
            })

        return jsonify({
            'success': True,
            'mode':    'month',
            'month':   month,
            'year':    year,
            'actual': {
                'days':            actual_days,
                'total_cost':      round(actual_cost, 2),
                'total_usage':     round(actual_usage, 2),
                'avg_daily_usage': round(avg_daily, 2),
            },
            'predicted': {
                'remaining_days':  remaining_days,
                'predicted_cost':  round(predicted_cost, 2),
                'predicted_usage': round(predicted_usage, 2),
            },
            'comparison': {
                'prev_month':      prev_month,
                'prev_month_cost': round(prev_cost, 2),
                'change_amount':   round(change_amount, 2),
                'change_percent':  round(change_pct, 2),
            },
            'gso_summary': {
                'penghematan_pct':    penghematan_pct,
                'est_hemat_per_hari': round(avg_biaya_aktual - avg_alokasi['biaya_optimal'], 0),
                'est_hemat_sebulan':  round((avg_biaya_aktual - avg_alokasi['biaya_optimal']) * 30, 0),
            },
            'daily_data': daily_data,
        }), 200

    except Exception as e:
        print(f'[dashboard] Month data error: {e}')
        return jsonify({'success': False, 'error': 'Failed to fetch month data'}), 500


# ============================================================
# YEAR VIEW
# ============================================================
@dashboard_bp.route('/year', methods=['GET'])
@token_required
def get_year_data(current_user):
    try:
        year = request.args.get('year')
        if year:
            year = int(year)
        else:
            latest = get_latest_records(1)
            year = latest[0]['record_date'].year if latest else datetime.now().year

        monthly_summary = get_monthly_summary(year)
        if not monthly_summary:
            return jsonify({'success': False, 'error': 'No data found for this year'}), 404

        monthly_data = []
        total_cost   = 0
        total_usage  = 0

        for m in monthly_summary:
            mc = float(m['total_cost'])  if m['total_cost']  else 0
            mu = float(m['total_usage']) if m['total_usage'] else 0
            monthly_data.append({
                'month':   int(m['month']),
                'cost':    round(mc, 2),
                'usage':   round(mu, 2),
                'records': int(m['total_records']),
                'type':    'actual',
            })
            total_cost  += mc
            total_usage += mu

        if len(monthly_data) < 12 and year == datetime.now().year:
            avg_cost  = total_cost  / len(monthly_data) if monthly_data else 0
            avg_usage = total_usage / len(monthly_data) if monthly_data else 0
            for month in range(len(monthly_data) + 1, 13):
                monthly_data.append({
                    'month': month, 'cost': round(avg_cost, 2),
                    'usage': round(avg_usage, 2), 'records': 0, 'type': 'estimated',
                })
                total_cost  += avg_cost
                total_usage += avg_usage

        carbon = total_usage * 0.85  # kg CO2/kWh Indonesia

        return jsonify({
            'success': True,
            'mode':    'year',
            'year':    year,
            'monthly_data': monthly_data,
            'total': {
                'cost':             round(total_cost, 2),
                'usage':            round(total_usage, 2),
                'carbon_footprint': round(carbon, 2),
            }
        }), 200

    except Exception as e:
        print(f'[dashboard] Year data error: {e}')
        return jsonify({'success': False, 'error': 'Failed to fetch year data'}), 500