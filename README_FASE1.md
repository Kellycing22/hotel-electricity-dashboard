# 🏨 Hotel Electricity Dashboard - FASE 1: Backend Core

## ✅ Files Generated (11 files)
```
backend/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── database.sql                # MySQL schema
├── .env.example                # Environment variables template
├── routes/
│   ├── __init__.py
│   ├── auth.py                 # Login/logout endpoints
│   ├── upload.py               # Upload Excel endpoints
│   └── dashboard.py            # Dashboard data endpoints (TODAY/MONTH/YEAR)
├── utils/
│   ├── __init__.py
│   └── database.py             # MySQL connection & queries
├── models/                     # ⚠️ YOU NEED TO ADD MODEL FILES HERE
│   ├── cnn_gso_model.h5       # (generate from Kaggle notebook)
│   ├── scaler_X.pkl           # (generate from Kaggle notebook)
│   └── scaler_y.pkl           # (generate from Kaggle notebook)
├── uploads/                    # Temporary upload folder
│   └── .gitkeep
└── data/                       # Database folder
    └── .gitkeep

.gitignore                      # Git ignore file
```

---

## 📋 **PREREQUISITES**

### 1. **Python 3.10+**
```bash
python --version  # Should be 3.10 or higher
```

### 2. **MySQL Server**
Install MySQL:
- **Windows**: Download from https://dev.mysql.com/downloads/installer/
- **Mac**: `brew install mysql`
- **Linux**: `sudo apt install mysql-server`

Start MySQL:
```bash
# Mac/Linux
sudo mysql

# Windows
net start mysql
```

---

## 🚀 **SETUP INSTRUCTIONS**

### **Step 1: Install Dependencies**
```bash
cd backend
pip install -r requirements.txt
```

### **Step 2: Setup MySQL Database**

1. **Login to MySQL:**
```bash
mysql -u root -p
```

2. **Create Database:**
```sql
source database.sql
```

Or manually:
```sql
CREATE DATABASE hotel_electricity;
USE hotel_electricity;
-- Then copy-paste the SQL from database.sql
```

3. **Verify tables created:**
```sql
SHOW TABLES;
-- Should show: users, datasets, electricity_records, model_trainings
```

4. **Exit MySQL:**
```sql
EXIT;
```

### **Step 3: Configure Environment Variables**

1. **Copy .env.example to .env:**
```bash
cp .env.example .env
```

2. **Edit .env file:**
```env
SECRET_KEY=randomly-generated-secret-key-here
FLASK_ENV=development
PORT=5000

FRONTEND_URL=http://localhost:3000

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password_here
DB_NAME=hotel_electricity
```

### **Step 4: Generate Model Files from Kaggle**

⚠️ **IMPORTANT**: You MUST generate these 3 files from your Kaggle notebook!

**Add this code at the end of your notebook:**
```python
# ========================================
# SAVE MODEL & SCALER
# ========================================

# 1. Save model CNN-GSO
best_model.save('cnn_gso_model.h5')
print("✅ Model saved: cnn_gso_model.h5")

# 2. Save scaler X (features)
import pickle
with open('scaler_X.pkl', 'wb') as f:
    pickle.dump(scaler_X, f)
print("✅ Scaler X saved: scaler_X.pkl")

# 3. Save scaler y (target)
with open('scaler_y.pkl', 'wb') as f:
    pickle.dump(scaler_y, f)
print("✅ Scaler y saved: scaler_y.pkl")
```

**Download these 3 files and place them in:**
```
backend/models/
├── cnn_gso_model.h5
├── scaler_X.pkl
└── scaler_y.pkl
```

### **Step 5: Run the Backend**
```bash
cd backend
python app.py
```

You should see:
```
🚀 Server starting on http://localhost:5000
📊 Dashboard API ready
```

---

## 🧪 **TEST THE API**

### **1. Health Check**
```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "message": "Hotel Electricity Dashboard API is running"
}
```

### **2. Test Login**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "manager",
    "password": "manager123"
  }'
```

Expected response:
```json
{
  "success": true,
  "token": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "user": {
    "id": 1,
    "username": "manager",
    "full_name": "Hotel Manager",
    "role": "manager"
  }
}
```

**Save the token!** You'll need it for other endpoints.

### **3. Test Upload (with Postman/Thunder Client)**

Since this requires file upload, use Postman:

- **Method:** POST
- **URL:** `http://localhost:5000/api/datasets/upload`
- **Headers:**
  - `Authorization: Bearer YOUR_TOKEN_HERE`
- **Body:** Form-data
  - Key: `file`
  - Type: File
  - Value: Select your Excel file

---

## 📊 **API ENDPOINTS**

### **Authentication**
```
POST   /api/auth/login       # Login
GET    /api/auth/verify      # Verify token
POST   /api/auth/logout      # Logout
```

### **Upload**
```
POST   /api/datasets/upload  # Upload Excel/CSV
GET    /api/datasets         # Get all datasets
GET    /api/datasets/{id}    # Get dataset detail
DELETE /api/datasets/{id}    # Delete dataset
```

### **Dashboard**
```
GET    /api/dashboard/today  # Get today's data
GET    /api/dashboard/month  # Get monthly data
GET    /api/dashboard/year   # Get yearly data
```

---

## 📝 **Excel File Format**

Your Excel file must have these columns (with semicolon separator for CSV):
```
DATE;DAY_OF_WEEK;IS_WEEKEND;IS_HOLIDAY;WEEK_OF_MONTH;MONTH;LWBP_USED;LWBP_PRICE;WBP_USED;WBP_PRICE;KVARH_USED;TOTAL_PRICE;TOTAL_BUILDING_ELECTRICITY;A_ELECTRICITY_USED;A_ELECTRICITY_PRICE;B_ELECTRICITY_USED;B_ELECTRICITY_PRICE;C_ELECTRICITY_USED;C_ELECTRICITY_PRICE
```

Example row:
```
2026-02-03;2;0;0;1;2;1,53;3804192;0,3;1118880;0,63;4923072;1,83;418,2;604173,54;34,7;50131,09;119,2;172208,24
```

---

## ⚠️ **TROUBLESHOOTING**

### **"ModuleNotFoundError"**
```bash
pip install -r requirements.txt
```

### **"Access denied for user 'root'@'localhost'"**
Check your `.env` file - make sure `DB_PASSWORD` is correct.

### **"Database 'hotel_electricity' doesn't exist"**
Run `database.sql` in MySQL.

### **"Missing model files"**
Generate the 3 model files from your Kaggle notebook (see Step 4).

---

## 🎯 **NEXT STEPS (FASE 2)**

After Phase 1 is working:
1. ✅ ML Integration (prediction.py, calculations.py)
2. ✅ Frontend (Dashboard UI with Tailwind CSS)
3. ✅ Deployment (Railway/Render + Vercel)

---

## 🆘 **Need Help?**

1. Check logs in terminal
2. Test each endpoint individually
3. Verify MySQL connection: `python -c "from utils.database import test_connection; test_connection()"`

---

**Status:** ✅ FASE 1 COMPLETE - Ready for testing!