import numpy as np
import pandas as pd
import os
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error
from tensorflow.keras.models import load_model

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'models')

WINDOW_SIZE = 14

FEATURE_COLS = [
    'DAY_OF_WEEK', 'IS_WEEKEND', 'IS_HOLIDAY', 'WEEK_OF_MONTH', 'MONTH',
    'LWBP_USED_KWH', 'WBP_USED_KWH', 'KVARH_USED',
    'A_ELECTRICITY_USED', 'B_ELECTRICITY_USED', 'C_ELECTRICITY_USED'
]

TARGET_COL = 'TOTAL_PLN_KWH'

ZONE_TARGET_COLS = {
    'zona_A': 'A_ELECTRICITY_USED',
    'zona_B': 'B_ELECTRICITY_USED',
    'zona_C': 'C_ELECTRICITY_USED',
}

# ─── Path model ───────────────────────────────────────────────────────────────
MODEL_PATHS_UTAMA = [
    os.path.join(MODEL_DIR, 'model_gedung_utama.h5'),
    os.path.join(MODEL_DIR, 'model_gedung_utama.keras'),
]

ZONE_MODEL_PATHS = {
    'zona_A': [os.path.join(MODEL_DIR, 'model_zona_a.h5'),
               os.path.join(MODEL_DIR, 'model_zona_a.keras')],
    'zona_B': [os.path.join(MODEL_DIR, 'model_zona_b.h5'),
               os.path.join(MODEL_DIR, 'model_zona_b.keras')],
    'zona_C': [os.path.join(MODEL_DIR, 'model_zona_c.h5'),
               os.path.join(MODEL_DIR, 'model_zona_c.keras')],
}

# ─── Path scaler ──────────────────────────────────────────────────────────────
SCALER_X_PATH = os.path.join(MODEL_DIR, 'scaler_X.pkl')

SCALER_Y_PATHS = {
    'utama':  os.path.join(MODEL_DIR, 'scaler_y_gedung_utama.pkl'),
    'zona_A': os.path.join(MODEL_DIR, 'scaler_y_zona_a.pkl'),
    'zona_B': os.path.join(MODEL_DIR, 'scaler_y_zona_b.pkl'),
    'zona_C': os.path.join(MODEL_DIR, 'scaler_y_zona_c.pkl'),
}

# ─── Path CSV prediksi NB2 ────────────────────────────────────────────────────
PRED_DIR = os.path.join(MODEL_DIR, 'predictions')

PRED_CSV_PATHS = {
    'utama':  os.path.join(PRED_DIR, 'prediksi_gedung_utama.csv'),
    'zona_A': os.path.join(PRED_DIR, 'prediksi_zona_a.csv'),
    'zona_B': os.path.join(PRED_DIR, 'prediksi_zona_b.csv'),
    'zona_C': os.path.join(PRED_DIR, 'prediksi_zona_c.csv'),
}

# ─── Cache global ─────────────────────────────────────────────────────────────
_model_utama = None
_zone_models = {}
_scaler_X    = None
_scaler_y    = {}
_nb2_metrics = None   # cache metrics NB2


# ─── Helper ───────────────────────────────────────────────────────────────────
def _find_model(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


# ─── Load artifacts ───────────────────────────────────────────────────────────
def load_artifacts():
    global _model_utama, _scaler_X, _scaler_y

    path = _find_model(MODEL_PATHS_UTAMA)
    if path:
        print(f"[prediction] Loading model utama: {os.path.basename(path)}")
        _model_utama = load_model(path, compile=False)
        print("[prediction] ✅ Model utama loaded")
    else:
        print("[prediction] ⚠️  Model utama tidak ditemukan")

    if os.path.exists(SCALER_X_PATH):
        _scaler_X = joblib.load(SCALER_X_PATH)
        print("[prediction] ✅ scaler_X loaded")
    else:
        print("[prediction] ⚠️  scaler_X.pkl tidak ditemukan")

    if os.path.exists(SCALER_Y_PATHS['utama']):
        _scaler_y['utama'] = joblib.load(SCALER_Y_PATHS['utama'])
        sy = _scaler_y['utama']
        print(f"[prediction] ✅ scaler_y utama loaded "
              f"(min={float(sy.data_min_[0]):.2f}, max={float(sy.data_max_[0]):.2f})")
    else:
        print("[prediction] ⚠️  scaler_y_gedung_utama.pkl tidak ditemukan")


def load_zone_artifacts():
    global _zone_models, _scaler_y

    for zone, paths in ZONE_MODEL_PATHS.items():
        path = _find_model(paths)
        if path:
            print(f"[prediction] Loading {zone}: {os.path.basename(path)}")
            _zone_models[zone] = load_model(path, compile=False)
            print(f"[prediction] ✅ {zone} loaded")
        else:
            print(f"[prediction] ⚠️  {zone} tidak ditemukan")

        sy_path = SCALER_Y_PATHS.get(zone)
        if sy_path and os.path.exists(sy_path):
            _scaler_y[zone] = joblib.load(sy_path)
            sy = _scaler_y[zone]
            print(f"[prediction] ✅ scaler_y {zone} loaded "
                  f"(min={float(sy.data_min_[0]):.2f}, max={float(sy.data_max_[0]):.2f})")
        else:
            print(f"[prediction] ⚠️  scaler_y_{zone}.pkl tidak ditemukan")


# ─── Getter ───────────────────────────────────────────────────────────────────
def get_model_utama():
    global _model_utama
    if _model_utama is None:
        load_artifacts()
    return _model_utama


def get_zone_models():
    if not _zone_models:
        load_zone_artifacts()
    return _zone_models


def get_scaler_X():
    global _scaler_X
    if _scaler_X is None:
        load_artifacts()
    return _scaler_X


def get_scaler_y(key='utama'):
    if key not in _scaler_y:
        if key == 'utama':
            load_artifacts()
        else:
            load_zone_artifacts()
    return _scaler_y.get(key)


# ─── Metrics dari NB2 (100% sama dengan Tabel 4.2 skripsi) ───────────────────
def get_nb2_metrics():
    """
    Load metrics langsung dari hasil prediksi NB2.
    Hasilnya identik dengan Tabel 4.2 di skripsi.
    Di-cache supaya tidak baca file berulang kali.
    """
    global _nb2_metrics
    if _nb2_metrics is not None:
        return _nb2_metrics

    path = PRED_CSV_PATHS['utama']
    if not os.path.exists(path):
        print(f'[prediction] ⚠️  {path} tidak ditemukan, pakai hitung manual')
        return None

    try:
        df_pred = pd.read_csv(path)
        print(f'[prediction] CSV NB2 kolom: {df_pred.columns.tolist()}')

        # Deteksi nama kolom otomatis
        actual_col, pred_col = None, None
        for c in df_pred.columns:
            cl = c.lower()
            if 'actual' in cl or 'aktual' in cl:
                actual_col = c
            if 'prediksi' in cl or 'pred' in cl:
                pred_col = c

        if actual_col is None or pred_col is None:
            print(f'[prediction] ⚠️  Kolom actual/prediksi tidak ditemukan')
            return None

        y_true = df_pred[actual_col].values.astype(float)
        y_pred = df_pred[pred_col].values.astype(float)

        mae  = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        mape = float(np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100)

        _nb2_metrics = {
            'MAE'     : round(mae,  4),
            'RMSE'    : round(rmse, 4),
            'MAPE'    : round(mape, 2),
            'kategori': (
                'Sangat Baik' if mape < 10 else
                'Baik'        if mape < 15 else
                'Cukup'       if mape < 20 else
                'Kurang Baik'
            ),
            'source'  : 'NB2'
        }

        print(f'[prediction] ✅ NB2 metrics loaded: '
              f'MAE={mae:.4f}, RMSE={rmse:.4f}, MAPE={mape:.2f}%')
        return _nb2_metrics

    except Exception as e:
        print(f'[prediction] get_nb2_metrics error: {e}')
        return None


def get_nb2_metrics_zona():
    """Load metrics per zona dari CSV NB2."""
    results = {}
    zona_map = {
        'zona_A': ('A_ELECTRICITY_USED', 'Zona A'),
        'zona_B': ('B_ELECTRICITY_USED', 'Zona B'),
        'zona_C': ('C_ELECTRICITY_USED', 'Zona C'),
    }
    for zone_key, (_, label) in zona_map.items():
        path = PRED_CSV_PATHS.get(zone_key)
        if not path or not os.path.exists(path):
            continue
        try:
            df_pred    = pd.read_csv(path)
            actual_col = next((c for c in df_pred.columns if 'actual' in c.lower() or 'aktual' in c.lower()), None)
            pred_col   = next((c for c in df_pred.columns if 'prediksi' in c.lower() or 'pred' in c.lower()), None)
            if actual_col and pred_col:
                yt   = df_pred[actual_col].values.astype(float)
                yp   = df_pred[pred_col].values.astype(float)
                mae  = float(mean_absolute_error(yt, yp))
                rmse = float(np.sqrt(mean_squared_error(yt, yp)))
                mape = float(np.mean(np.abs((yt - yp) / (yt + 1e-8))) * 100)
                results[zone_key] = {
                    'MAE' : round(mae,  4),
                    'RMSE': round(rmse, 4),
                    'MAPE': round(mape, 2),
                    'kategori': 'Sangat Baik' if mape < 10 else 'Baik' if mape < 15 else 'Cukup',
                }
        except Exception as e:
            print(f'[prediction] metrics {zone_key} error: {e}')
    return results


# ─── Prepare df ───────────────────────────────────────────────────────────────
def _prepare_df(df):
    """Konversi MWh → kWh dan buat TOTAL_PLN_KWH."""
    df = df.copy()
    if 'LWBP_USED_KWH' not in df.columns and 'LWBP_USED' in df.columns:
        df['LWBP_USED_KWH'] = df['LWBP_USED'] * 1000
    if 'WBP_USED_KWH' not in df.columns and 'WBP_USED' in df.columns:
        df['WBP_USED_KWH'] = df['WBP_USED'] * 1000
    if 'LWBP_USED_KWH' in df.columns and 'WBP_USED_KWH' in df.columns:
        df['TOTAL_PLN_KWH'] = df['LWBP_USED_KWH'] + df['WBP_USED_KWH']
    return df


# ─── Prediksi ─────────────────────────────────────────────────────────────────
def predict_next_day(df):
    """Prediksi total building electricity 1 hari ke depan (kWh)."""
    df       = _prepare_df(df)
    model    = get_model_utama()
    scaler_X = get_scaler_X()
    scaler_y = get_scaler_y('utama')

    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing or len(df) < WINDOW_SIZE:
        fallback = round(float(df[TARGET_COL].mean()), 2) if TARGET_COL in df.columns else 2404.42
        print(f"[prediction] fallback predict_next_day: {fallback}")
        return fallback

    try:
        X_raw    = df[FEATURE_COLS].values[-WINDOW_SIZE:]
        X_scaled = scaler_X.transform(X_raw).reshape(1, WINDOW_SIZE, len(FEATURE_COLS))

        if model is None or scaler_y is None:
            return round(float(df[TARGET_COL].mean()), 2) if TARGET_COL in df.columns else 2404.42

        pred_raw = float(model.predict(X_scaled, verbose=0)[0][0])
        pred     = float(scaler_y.inverse_transform([[pred_raw]])[0][0])

        print(f'[prediction] pred_raw={pred_raw:.4f} → pred={pred:.2f} kWh')
        return round(pred, 2)

    except Exception as e:
        print(f"[prediction] predict_next_day error: {e}")
        return round(float(df[TARGET_COL].mean()), 2) if TARGET_COL in df.columns else 2404.42


def predict_zones(df):
    """Prediksi konsumsi per zona (kWh)."""
    df          = _prepare_df(df)
    zone_models = get_zone_models()
    scaler_X    = get_scaler_X()
    results     = {}

    for zone, target_col in ZONE_TARGET_COLS.items():
        try:
            scaler_y = get_scaler_y(zone)
            if (zone in zone_models
                    and scaler_X is not None
                    and scaler_y is not None
                    and target_col in df.columns
                    and len(df) >= WINDOW_SIZE):

                X_raw    = df[FEATURE_COLS].values[-WINDOW_SIZE:]
                X_scaled = scaler_X.transform(X_raw).reshape(1, WINDOW_SIZE, len(FEATURE_COLS))
                pred_raw = float(zone_models[zone].predict(X_scaled, verbose=0)[0][0])
                pred     = float(scaler_y.inverse_transform([[pred_raw]])[0][0])

                print(f'[prediction] {zone}: pred_raw={pred_raw:.4f} → {pred:.2f} kWh')
                results[zone] = round(pred, 2)
            else:
                results[zone] = round(float(df[target_col].mean()), 2) if target_col in df.columns else 0.0

        except Exception as e:
            print(f"[prediction] predict_zones {zone} error: {e}")
            results[zone] = round(float(df[target_col].mean()), 2) if target_col in df.columns else 0.0

    return results


def predict_from_df(df):
    """Prediksi seluruh window dari df — untuk grafik historis."""
    df       = _prepare_df(df)
    model    = get_model_utama()
    scaler_X = get_scaler_X()
    scaler_y = get_scaler_y('utama')

    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing or len(df) < WINDOW_SIZE:
        raise ValueError(f"Data tidak cukup atau kolom kurang: {missing}")

    if model is None or scaler_X is None or scaler_y is None:
        vals  = df[TARGET_COL].values[WINDOW_SIZE:].tolist() if TARGET_COL in df.columns else []
        dates = df['DATE'].dt.strftime('%Y-%m-%d').tolist()[WINDOW_SIZE:] if 'DATE' in df.columns else []
        return {'predictions': [round(v, 4) for v in vals], 'dates': dates, 'count': len(vals)}

    X_all    = df[FEATURE_COLS].values
    X_scaled = scaler_X.transform(X_all)

    sequences = np.array([
        X_scaled[i - WINDOW_SIZE:i]
        for i in range(WINDOW_SIZE, len(X_scaled))
    ])

    pred_raw    = model.predict(sequences, verbose=0).flatten()
    predictions = scaler_y.inverse_transform(
        pred_raw.reshape(-1, 1)
    ).flatten().tolist()

    print(f'[prediction] predict_from_df: mean={np.mean(predictions):.2f} kWh')

    dates = []
    if 'DATE' in df.columns:
        dates = df['DATE'].dt.strftime('%Y-%m-%d').tolist()[WINDOW_SIZE:]

    return {
        'predictions': [round(v, 4) for v in predictions],
        'dates': dates,
        'count': len(predictions)
    }