-- ================================================
-- Hotel Electricity Dashboard - Database Schema
-- ================================================

CREATE DATABASE IF NOT EXISTS hotel_electricity;
USE hotel_electricity;

-- ================================================
-- 1. USERS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role ENUM('manager', 'admin') DEFAULT 'manager',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 2. DATASETS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    week INT NOT NULL,
    year INT NOT NULL,
    records_count INT DEFAULT 0,
    status ENUM('uploaded', 'validated', 'used_for_training') DEFAULT 'uploaded',
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_week_year (week, year),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 3. ELECTRICITY RECORDS TABLE
-- ================================================
CREATE TABLE IF NOT EXISTS electricity_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    record_date DATE NOT NULL,
    day_of_week INT,
    is_weekend BOOLEAN DEFAULT FALSE,
    is_holiday BOOLEAN DEFAULT FALSE,
    week_of_month INT,
    month INT,
    
    -- Consumption data
    lwbp_used DECIMAL(10, 2),
    lwbp_price DECIMAL(15, 2),
    wbp_used DECIMAL(10, 2),
    wbp_price DECIMAL(15, 2),
    kvarh_used DECIMAL(10, 2),
    total_price DECIMAL(15, 2),
    
    -- Target variable
    total_building_electricity DECIMAL(10, 2),
    
    -- Area breakdown
    a_electricity_used DECIMAL(10, 2),
    a_electricity_price DECIMAL(15, 2),
    b_electricity_used DECIMAL(10, 2),
    b_electricity_price DECIMAL(15, 2),
    c_electricity_used DECIMAL(10, 2),
    c_electricity_price DECIMAL(15, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    UNIQUE KEY unique_date (dataset_id, record_date),
    INDEX idx_date (record_date),
    INDEX idx_dataset (dataset_id),
    INDEX idx_month_year (month, record_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 4. MODEL TRAININGS TABLE (Optional - Phase 2)
-- ================================================
CREATE TABLE IF NOT EXISTS model_trainings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT,
    mae DECIMAL(10, 4),
    mse DECIMAL(10, 4),
    rmse DECIMAL(10, 4),
    status ENUM('running', 'completed', 'failed') DEFAULT 'running',
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_dataset (dataset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================
-- 5. INSERT DEFAULT USER (Manager)
-- ================================================
-- Password: manager123 (hashed with bcrypt)
-- You should change this in production!
INSERT INTO users (username, password_hash, full_name, role) VALUES
('manager', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5QRwpM8ZjJw6G', 'Hotel Manager', 'manager')
ON DUPLICATE KEY UPDATE username=username;

-- ================================================
-- 6. SAMPLE QUERIES (for testing)
-- ================================================

-- Get all records for a specific date range
-- SELECT * FROM electricity_records 
-- WHERE record_date BETWEEN '2026-02-01' AND '2026-02-28'
-- ORDER BY record_date;

-- Get monthly summary
-- SELECT 
--     YEAR(record_date) as year,
--     MONTH(record_date) as month,
--     COUNT(*) as total_records,
--     SUM(total_price) as total_cost,
--     AVG(total_building_electricity) as avg_usage
-- FROM electricity_records
-- GROUP BY YEAR(record_date), MONTH(record_date)
-- ORDER BY year DESC, month DESC;

-- Get latest 7 days for prediction
-- SELECT * FROM electricity_records
-- ORDER BY record_date DESC
-- LIMIT 7;