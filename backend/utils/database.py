import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'hotel_electricity'),
    'port': int(os.getenv('DB_PORT', 3306))
}

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    connection = None
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        yield connection
    except Error as e:
        print(f"Database error: {e}")
        raise
    finally:
        if connection and connection.is_connected():
            connection.close()

def execute_query(query, params=None, fetch=False):
    """Execute a single query"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch:
                result = cursor.fetchall()
                cursor.close()
                return result
            else:
                conn.commit()
                last_id = cursor.lastrowid
                cursor.close()
                return last_id
    except Error as e:
        print(f"Query execution error: {e}")
        raise

def execute_many(query, data):
    """Execute batch insert"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data)
            conn.commit()
            cursor.close()
            return cursor.rowcount
    except Error as e:
        print(f"Batch execution error: {e}")
        raise

# ============================================
# USER QUERIES
# ============================================

def get_user_by_username(username):
    """Get user by username"""
    query = "SELECT * FROM users WHERE username = %s"
    result = execute_query(query, (username,), fetch=True)
    return result[0] if result else None

def get_user_by_id(user_id):
    """Get user by ID"""
    query = "SELECT * FROM users WHERE id = %s"
    result = execute_query(query, (user_id,), fetch=True)
    return result[0] if result else None

def create_user(username, password_hash, full_name=None, role='manager'):
    """Create new user"""
    query = """
        INSERT INTO users (username, password_hash, full_name, role)
        VALUES (%s, %s, %s, %s)
    """
    return execute_query(query, (username, password_hash, full_name, role))

# ============================================
# DATASET QUERIES
# ============================================

def create_dataset(user_id, filename, week, year):
    """Create new dataset entry"""
    query = """
        INSERT INTO datasets (user_id, filename, week, year)
        VALUES (%s, %s, %s, %s)
    """
    return execute_query(query, (user_id, filename, week, year))

def update_dataset_records_count(dataset_id, count):
    """Update records count for a dataset"""
    query = "UPDATE datasets SET records_count = %s WHERE id = %s"
    execute_query(query, (count, dataset_id))

def get_datasets_by_user(user_id, limit=10):
    """Get all datasets uploaded by user"""
    query = """
        SELECT id, filename, week, year, records_count, status, uploaded_at
        FROM datasets
        WHERE user_id = %s
        ORDER BY uploaded_at DESC
        LIMIT %s
    """
    return execute_query(query, (user_id, limit), fetch=True)

def get_dataset_by_id(dataset_id):
    """Get dataset by ID"""
    query = "SELECT * FROM datasets WHERE id = %s"
    result = execute_query(query, (dataset_id,), fetch=True)
    return result[0] if result else None

def delete_dataset(dataset_id):
    """Delete dataset (will cascade to records)"""
    query = "DELETE FROM datasets WHERE id = %s AND status != 'used_for_training'"
    execute_query(query, (dataset_id,))

# ============================================
# ELECTRICITY RECORDS QUERIES
# ============================================

def insert_electricity_records(records):
    """Batch insert electricity records"""
    query = """
        INSERT INTO electricity_records (
            dataset_id, record_date, day_of_week, is_weekend, is_holiday,
            week_of_month, month, lwbp_used, lwbp_price, wbp_used, wbp_price,
            kvarh_used, total_price, total_building_electricity,
            a_electricity_used, a_electricity_price,
            b_electricity_used, b_electricity_price,
            c_electricity_used, c_electricity_price
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
    """
    return execute_many(query, records)

def get_records_by_dataset(dataset_id):
    """Get all records for a dataset"""
    query = """
        SELECT * FROM electricity_records
        WHERE dataset_id = %s
        ORDER BY record_date
    """
    return execute_query(query, (dataset_id,), fetch=True)

def get_latest_records(limit=7):
    """Get latest N records for prediction"""
    query = """
        SELECT * FROM electricity_records
        ORDER BY record_date DESC
        LIMIT %s
    """
    return execute_query(query, (limit,), fetch=True)

def get_records_by_date_range(start_date, end_date):
    """Get records within date range"""
    query = """
        SELECT * FROM electricity_records
        WHERE record_date BETWEEN %s AND %s
        ORDER BY record_date
    """
    return execute_query(query, (start_date, end_date), fetch=True)

def get_records_by_month(month, year):
    """Get all records for a specific month"""
    query = """
        SELECT * FROM electricity_records
        WHERE month = %s AND YEAR(record_date) = %s
        ORDER BY record_date
    """
    return execute_query(query, (month, year), fetch=True)

def get_records_by_year(year):
    """Get all records for a specific year"""
    query = """
        SELECT * FROM electricity_records
        WHERE YEAR(record_date) = %s
        ORDER BY record_date
    """
    return execute_query(query, (year,), fetch=True)

def get_monthly_summary(year):
    """Get monthly aggregated data for a year"""
    query = """
        SELECT 
            MONTH(record_date) as month,
            COUNT(*) as total_records,
            SUM(total_price) as total_cost,
            SUM(total_building_electricity) as total_usage,
            AVG(total_building_electricity) as avg_usage,
            SUM(a_electricity_used) as total_area_a,
            SUM(b_electricity_used) as total_area_b,
            SUM(c_electricity_used) as total_area_c
        FROM electricity_records
        WHERE YEAR(record_date) = %s
        GROUP BY MONTH(record_date)
        ORDER BY month
    """
    return execute_query(query, (year,), fetch=True)

# ============================================
# UTILITY FUNCTIONS
# ============================================

def test_connection():
    """Test database connection"""
    try:
        with get_db_connection() as conn:
            if conn.is_connected():
                print("Database connection successful")
                return True
    except Error as e:
        print(f"Database connection failed: {e}")
        return False

if __name__ == '__main__':
    # Test connection
    test_connection()
    
def get_prediction_history(user_id, limit=10):
    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM prediction_history
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        rows = cursor.fetchall()
        for r in rows:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat()
        return rows

def save_prediction_history(data):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prediction_history 
            (user_id, dataset_filename, total_rows, next_day_kwh, next_day_cost,
             mae, rmse, mape, avg_daily, zona_a_avg, zona_b_avg, zona_c_avg)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data['user_id'], data['dataset_filename'], data['total_rows'],
            data['next_day_kwh'], data['next_day_cost'],
            data['mae'], data['rmse'], data['mape'],
            data['avg_daily'], data['zona_a_avg'], data['zona_b_avg'], data['zona_c_avg']
        ))
        conn.commit()