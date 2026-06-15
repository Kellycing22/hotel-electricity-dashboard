from flask import Blueprint, request, jsonify
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from routes.auth import token_required
from utils.database import (
    create_dataset,
    update_dataset_records_count,
    insert_electricity_records,
    get_datasets_by_user,
    get_dataset_by_id,
    get_records_by_dataset,
    delete_dataset
)
from utils.anomaly_detection import (
    deteksi_anomali,
    bersihkan_anomali_kritis,
    format_untuk_dashboard,
)

upload_bp = Blueprint('upload', __name__)

UPLOAD_FOLDER      = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_excel_file(filepath):
    """
    Parse Excel/CSV file dan validasi kolom.
    Null value check dipindah ke setelah anomaly cleaning.
    """
    try:
        if filepath.endswith('.csv'):
            for sep in ['\t', ';', ',']:
                try:
                    df = pd.read_csv(filepath, sep=sep, encoding='utf-8')
                    if df.shape[1] >= 5:
                        break
                except Exception:
                    continue
            else:
                df = pd.read_csv(filepath, encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.replace(' ', '_')

        # ── FIX 1: Date parsing lebih fleksibel ─────────────────────────────
        # Format asli '%d/%m/%y' akan gagal untuk format lain (misal: 2024-01-15)
        if 'DATE' in df.columns:
            df['DATE'] = pd.to_datetime(df['DATE'], infer_datetime_format=True, errors='coerce')
            # Fallback manual jika masih ada NaT
            if df['DATE'].isna().any():
                for fmt in ['%d/%m/%y', '%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y']:
                    try:
                        df['DATE'] = pd.to_datetime(df['DATE'], format=fmt, errors='coerce')
                        if df['DATE'].notna().sum() > df['DATE'].isna().sum():
                            break
                    except Exception:
                        continue

        # ── Konversi numerik ─────────────────────────────────────────────────
        numeric_cols = df.columns.drop('DATE', errors='ignore')
        for col in numeric_cols:
            try:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.strip()
                    .str.replace('.', '', regex=False)
                    .str.replace(',', '.', regex=False)
                    .astype(float)
                )
            except Exception:
                pass

        # ── FIX 2: Tambah kolom kWh setelah parsing ─────────────────────────
        # LWBP_USED dan WBP_USED dari Excel dalam MWh
        # Tambahkan kolom kWh agar tidak perlu konversi berulang di route lain
        if 'LWBP_USED' in df.columns:
            df['LWBP_USED_KWH'] = df['LWBP_USED'] * 1000
        if 'WBP_USED' in df.columns:
            df['WBP_USED_KWH'] = df['WBP_USED'] * 1000
        if 'LWBP_USED_KWH' in df.columns and 'WBP_USED_KWH' in df.columns:
            df['TOTAL_PLN_KWH'] = df['LWBP_USED_KWH'] + df['WBP_USED_KWH']

        # ── Validasi kolom wajib ─────────────────────────────────────────────
        required_cols = [
            'DATE', 'DAY_OF_WEEK', 'IS_WEEKEND', 'IS_HOLIDAY',
            'WEEK_OF_MONTH', 'MONTH', 'LWBP_USED', 'LWBP_PRICE',
            'WBP_USED', 'WBP_PRICE', 'KVARH_USED', 'TOTAL_PRICE',
            'TOTAL_BUILDING_ELECTRICITY', 'A_ELECTRICITY_USED',
            'A_ELECTRICITY_PRICE', 'B_ELECTRICITY_USED',
            'B_ELECTRICITY_PRICE', 'C_ELECTRICITY_USED',
            'C_ELECTRICITY_PRICE'
        ]

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return None, f"Missing columns: {', '.join(missing_cols)}"

        first_date = df['DATE'].iloc[0]
        week       = first_date.isocalendar()[1]
        year       = first_date.year

        return {
            'dataframe':     df,
            'week':          week,
            'year':          year,
            'records_count': len(df)
        }, None

    except Exception as e:
        return None, f"Error parsing file: {str(e)}"


# ============================================================
# UPLOAD DATASET
# ============================================================
@upload_bp.route('/datasets/upload', methods=['POST'])
@token_required
def upload_dataset(current_user):
    print("=" * 50)
    print("UPLOAD REQUEST RECEIVED")
    print("Files:", request.files)
    print("=" * 50)

    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only CSV, XLS, XLSX are allowed'
            }), 400

        filename  = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename  = f"{timestamp}_{filename}"
        filepath  = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        result, error = parse_excel_file(filepath)
        if error:
            os.remove(filepath)
            return jsonify({'success': False, 'error': error}), 400

        df            = result['dataframe']
        week          = result['week']
        year          = result['year']
        records_count = result['records_count']

        # ── Anomaly detection ────────────────────────────────────────────────
        hasil_anomali = deteksi_anomali(df)
        data_anomali  = format_untuk_dashboard(hasil_anomali)
        df, n_dibersihkan = bersihkan_anomali_kritis(df)

        # ── Cek null setelah cleaning ────────────────────────────────────────
        if df.isnull().any().any():
            os.remove(filepath)
            return jsonify({
                'success': False,
                'error': 'Dataset masih mengandung null values setelah cleaning.'
            }), 400

        # ── Simpan ke database ───────────────────────────────────────────────
        dataset_id = create_dataset(
            user_id=current_user['id'],
            filename=filename,
            week=week,
            year=year
        )

        records = []
        for _, row in df.iterrows():
            records.append((
                dataset_id,
                row['DATE'].date(),
                int(row['DAY_OF_WEEK']),
                bool(row['IS_WEEKEND']),
                bool(row['IS_HOLIDAY']),
                int(row['WEEK_OF_MONTH']),
                int(row['MONTH']),
                float(row['LWBP_USED']),          # MWh — nilai asli
                float(row['LWBP_PRICE']),
                float(row['WBP_USED']),            # MWh — nilai asli
                float(row['WBP_PRICE']),
                float(row['KVARH_USED']),
                float(row['TOTAL_PRICE']),
                float(row['TOTAL_BUILDING_ELECTRICITY']),
                float(row['A_ELECTRICITY_USED']),
                float(row['A_ELECTRICITY_PRICE']),
                float(row['B_ELECTRICITY_USED']),
                float(row['B_ELECTRICITY_PRICE']),
                float(row['C_ELECTRICITY_USED']),
                float(row['C_ELECTRICITY_PRICE'])
            ))

        insert_electricity_records(records)
        update_dataset_records_count(dataset_id, records_count)

        # ── Ringkasan anomali ────────────────────────────────────────────────
        pesan_anomali = ''
        if n_dibersihkan > 0:
            pesan_anomali += f'{n_dibersihkan} nilai kritis otomatis dibersihkan.'
        if data_anomali['ada_anomali']:
            pesan_anomali += (
                f' {data_anomali["total_anomali"]} anomali terdeteksi'
                f' ({data_anomali["jumlah_kritis"]} kritis).'
            )

        # ── Log ringkasan ────────────────────────────────────────────────────
        print(f'[upload] ✅ {records_count} records disimpan')
        if 'TOTAL_PLN_KWH' in df.columns:
            print(f'[upload]    TOTAL_PLN_KWH mean: {df["TOTAL_PLN_KWH"].mean():.2f} kWh')

        return jsonify({
            'success':       True,
            'dataset_id':    dataset_id,
            'filename':      file.filename,
            'week':          week,
            'year':          year,
            'records_count': records_count,
            'n_dibersihkan': n_dibersihkan,
            'anomali':       data_anomali,
            'pesan_anomali': pesan_anomali,
        }), 200

    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'success': False, 'error': 'Upload failed'}), 500


# ============================================================
# GET DATASETS
# ============================================================
@upload_bp.route('/datasets', methods=['GET'])
@token_required
def get_datasets(current_user):
    try:
        limit    = request.args.get('limit', 10, type=int)
        datasets = get_datasets_by_user(current_user['id'], limit)
        return jsonify({'success': True, 'datasets': datasets}), 200
    except Exception as e:
        print(f"Get datasets error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch datasets'}), 500


# ============================================================
# GET DATASET BY ID
# ============================================================
@upload_bp.route('/datasets/<int:dataset_id>', methods=['GET'])
@token_required
def get_dataset_detail(current_user, dataset_id):
    try:
        dataset = get_dataset_by_id(dataset_id)
        if not dataset:
            return jsonify({'success': False, 'error': 'Dataset not found'}), 404
        if dataset['user_id'] != current_user['id']:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        records = get_records_by_dataset(dataset_id)
        return jsonify({'success': True, 'dataset': dataset, 'records': records}), 200
    except Exception as e:
        print(f"Get dataset detail error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch dataset'}), 500


# ============================================================
# DELETE DATASET
# ============================================================
@upload_bp.route('/datasets/<int:dataset_id>', methods=['DELETE'])
@token_required
def delete_dataset_endpoint(current_user, dataset_id):
    try:
        dataset = get_dataset_by_id(dataset_id)
        if not dataset:
            return jsonify({'success': False, 'error': 'Dataset not found'}), 404
        if dataset['user_id'] != current_user['id']:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        if dataset['status'] == 'used_for_training':
            return jsonify({
                'success': False,
                'error': 'Cannot delete dataset that has been used for training'
            }), 400
        delete_dataset(dataset_id)
        return jsonify({'success': True, 'message': 'Dataset deleted successfully'}), 200
    except Exception as e:
        print(f"Delete dataset error: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete dataset'}), 500