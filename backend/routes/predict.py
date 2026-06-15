from flask import Blueprint, request, jsonify
import pandas as pd
import numpy as np
import os
import traceback
from routes.auth import token_required
from utils.preprocessing import parse_uploaded_csv, FEATURE_COLS, WINDOW_SIZE
from utils.prediction     import (predict_from_df, predict_next_day, predict_zones,
                                   _prepare_df, get_nb2_metrics, get_nb2_metrics_zona)
from utils.calculations   import (calculate_metrics, summarize_data, zone_breakdown,
                                   generate_recommendation, calculate_cost_breakdown,
                                   estimate_cost_from_prediction)

predict_bp    = Blueprint('predict', __name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')

TARIF_LWBP  = 2400 * 1036 / 1000
TARIF_WBP   = 2400 * 1554 / 1000
TARIF_RESTO = 1444.7

PRED_MIN = 1030.0
PRED_MAX = 4070.0


def _clip_predictions(predictions_kwh, df):
    if not predictions_kwh:
        return predictions_kwh
    if 'TOTAL_PLN_KWH' in df.columns:
        m  = df['TOTAL_PLN_KWH'].mean()
        s  = df['TOTAL_PLN_KWH'].std()
        lo = max(PRED_MIN, m - 3 * s)
        hi = min(PRED_MAX, m + 3 * s)
    else:
        lo, hi = PRED_MIN, PRED_MAX
    return [round(max(lo, min(hi, v)), 2) for v in predictions_kwh]


def _clip_single(val, df):
    if 'TOTAL_PLN_KWH' in df.columns:
        m  = df['TOTAL_PLN_KWH'].mean()
        s  = df['TOTAL_PLN_KWH'].std()
        lo = max(PRED_MIN, m - 3 * s)
        hi = min(PRED_MAX, m + 3 * s)
    else:
        lo, hi = PRED_MIN, PRED_MAX
    return round(max(lo, min(hi, val)), 2)


@predict_bp.route('/api/predict/upload', methods=['POST'])
@token_required
def predict_upload(current_user):
    if 'file' not in request.files:
        return jsonify({'error': 'Tidak ada file yang diupload.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nama file kosong.'}), 400
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        return jsonify({'error': 'Hanya file CSV, XLSX, atau XLS yang diterima.'}), 400

    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(save_path)

    try:
        df = parse_uploaded_csv(save_path)
        df = _prepare_df(df)

        # Grafik prediksi historis
        result          = predict_from_df(df)
        predictions_kwh = _clip_predictions(
            [round(v, 2) for v in result['predictions']], df
        )

        # ── Metrics dari NB2 (100% sama dengan Tabel 4.2 skripsi) ──
        metrics = get_nb2_metrics()
        if metrics is None:
            # Fallback hitung manual jika CSV NB2 belum ada
            from utils.predict_helpers import _hitung_metrics
            metrics = _hitung_metrics(df, predictions_kwh)

        # Data hari terakhir
        last_row   = df.iloc[-1].to_dict()
        today_kwh  = float(last_row.get('TOTAL_PLN_KWH',
                     last_row.get('TOTAL_BUILDING_ELECTRICITY', 0)))
        today_cost = calculate_cost_breakdown(last_row)

        # Prediksi besok
        next_day_kwh     = _clip_single(predict_next_day(df), df)
        zone_predictions = predict_zones(df)
        zona_a = zone_predictions.get('zona_A', 0)
        zona_b = zone_predictions.get('zona_B', 0)
        zona_c = zone_predictions.get('zona_C', 0)

        # Rasio LWBP/WBP
        if 'LWBP_USED_KWH' in df.columns and 'WBP_USED_KWH' in df.columns:
            la  = df['LWBP_USED_KWH'].mean()
            wa  = df['WBP_USED_KWH'].mean()
            tot = la + wa
            rl  = la / tot if tot > 0 else 0.8
            rw  = wa / tot if tot > 0 else 0.2
        else:
            rl, rw = 0.8, 0.2

        pred_lwbp = round(next_day_kwh * rl, 2)
        pred_wbp  = round(next_day_kwh * rw, 2)

        biaya_lwbp   = round(pred_lwbp * TARIF_LWBP,  2)
        biaya_wbp    = round(pred_wbp  * TARIF_WBP,   2)
        biaya_zona_a = round(zona_a    * TARIF_RESTO,  2)
        biaya_zona_b = round(zona_b    * TARIF_RESTO,  2)
        biaya_zona_c = round(zona_c    * TARIF_RESTO,  2)
        total_biaya  = round(biaya_lwbp + biaya_wbp + biaya_zona_a + biaya_zona_b + biaya_zona_c, 2)

        next_day_cost = {
            'lwbp_cost'  : biaya_lwbp,
            'wbp_cost'   : biaya_wbp,
            'area_a_cost': biaya_zona_a,
            'area_b_cost': biaya_zona_b,
            'area_c_cost': biaya_zona_c,
            'total_cost' : total_biaya
        }

        summary        = summarize_data(df)
        zones          = zone_breakdown(df)
        recommendation = generate_recommendation(next_day_kwh, summary.get('avg_daily'))

        # Metrics per zona dari NB2
        zona_metrics = get_nb2_metrics_zona()

        try:
            from utils.database import save_prediction_history
            save_prediction_history({
                'user_id':          current_user['id'],
                'dataset_filename': file.filename,
                'total_rows':       len(df),
                'next_day_kwh':     next_day_kwh,
                'next_day_cost':    total_biaya,
                'mae':              metrics['MAE']  if metrics else None,
                'rmse':             metrics['RMSE'] if metrics else None,
                'mape':             metrics['MAPE'] if metrics else None,
                'avg_daily':        summary.get('avg_daily'),
                'zona_a_avg':       summary.get('zone_a_avg'),
                'zona_b_avg':       summary.get('zone_b_avg'),
                'zona_c_avg':       summary.get('zone_c_avg'),
            })
        except Exception as e:
            print(f'[predict] Warning: gagal simpan history: {e}')

        return jsonify({
            'success'          : True,
            'total_rows'       : len(df),
            'predictions'      : predictions_kwh,
            'dates'            : result['dates'],
            'count'            : result['count'],
            'today_kwh'        : today_kwh,
            'today_cost'       : today_cost,
            'next_day'         : next_day_kwh,
            'next_day_cost'    : next_day_cost,
            'zone_predictions' : {
                'pred_lwbp': pred_lwbp,
                'pred_wbp' : pred_wbp,
                'zona_A'   : zona_a,
                'zona_B'   : zona_b,
                'zona_C'   : zona_c,
            },
            'metrics'          : metrics,
            'zona_metrics'     : zona_metrics,
            'summary'          : summary,
            'zones'            : zones,
            'recommendation'   : recommendation
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 422
    except Exception:
        return jsonify({'error': 'Terjadi kesalahan server.',
                        'detail': traceback.format_exc()}), 500


@predict_bp.route('/api/predict/manual', methods=['POST'])
def predict_manual():
    body = request.get_json(silent=True)
    if not body or 'data' not in body:
        return jsonify({'error': 'Body JSON harus berisi key "data".'}), 400
    rows = body['data']
    if len(rows) < 14:
        return jsonify({'error': f'Minimal 14 baris, hanya ada {len(rows)}.'}), 422
    try:
        df = pd.DataFrame(rows)
        if 'LWBP_USED' in df.columns and 'LWBP_USED_KWH' not in df.columns:
            df['LWBP_USED_KWH'] = df['LWBP_USED'].astype(float) * 1000
        if 'WBP_USED' in df.columns and 'WBP_USED_KWH' not in df.columns:
            df['WBP_USED_KWH'] = df['WBP_USED'].astype(float) * 1000
        if 'LWBP_USED_KWH' in df.columns and 'WBP_USED_KWH' in df.columns:
            df['TOTAL_PLN_KWH'] = df['LWBP_USED_KWH'] + df['WBP_USED_KWH']
        missing = [c for c in FEATURE_COLS if c not in df.columns]
        if missing:
            return jsonify({'error': f'Kolom tidak lengkap: {missing}'}), 422
        df[FEATURE_COLS]  = df[FEATURE_COLS].astype(float)
        next_day_kwh      = _clip_single(predict_next_day(df), df)
        zone_predictions  = predict_zones(df)
        next_day_cost     = estimate_cost_from_prediction(next_day_kwh, df)
        summary           = summarize_data(df)
        recommendation    = generate_recommendation(next_day_kwh, summary.get('avg_daily'))
        return jsonify({
            'success'         : True,
            'next_day'        : next_day_kwh,
            'zone_predictions': zone_predictions,
            'next_day_cost'   : next_day_cost,
            'recommendation'  : recommendation
        })
    except Exception:
        return jsonify({'error': 'Terjadi kesalahan.', 'detail': traceback.format_exc()}), 500


@predict_bp.route('/api/predict/info', methods=['GET'])
def model_info():
    return jsonify({
        'model'      : 'CNN-GSO',
        'target'     : 'TOTAL_PLN_KWH (kWh)',
        'features'   : FEATURE_COLS,
        'window_size': WINDOW_SIZE,
        'zona_models': ['zona_A', 'zona_B', 'zona_C'],
    })


@predict_bp.route('/api/predict/history', methods=['GET'])
@token_required
def get_history(current_user):
    try:
        from utils.database import get_prediction_history
        limit = request.args.get('limit', 10, type=int)
        rows  = get_prediction_history(current_user['id'], limit)
        return jsonify({'success': True, 'history': rows})
    except Exception as e:
        print(f'[history] error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500