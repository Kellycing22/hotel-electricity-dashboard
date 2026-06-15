from flask import Blueprint, request, jsonify
import jwt
import bcrypt
from datetime import datetime, timedelta
import os
from functools import wraps
from utils.database import get_user_by_username, get_user_by_id

auth_bp = Blueprint('auth', __name__)

SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# ============================================
# JWT DECORATOR
# ============================================

def token_required(f):
    """Decorator to protect routes with JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            # Decode token
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user = get_user_by_id(data['user_id'])
            
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# ============================================
# LOGIN ENDPOINT
# ============================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login endpoint
    
    Request body:
    {
        "username": "manager",
        "password": "manager123"
    }
    
    Response:
    {
        "success": true,
        "token": "JWT_TOKEN",
        "user": {
            "id": 1,
            "username": "manager",
            "full_name": "Hotel Manager",
            "role": "manager"
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        # Get user from database
        user = get_user_by_username(username)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        # Generate JWT token (expires in 24 hours)
        token = jwt.encode({
            'user_id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'full_name': user.get('full_name'),
                'role': user['role']
            }
        }), 200
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500

# ============================================
# VERIFY TOKEN ENDPOINT
# ============================================

@auth_bp.route('/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    """
    Verify if token is still valid
    
    Response:
    {
        "success": true,
        "user": {
            "id": 1,
            "username": "manager",
            "full_name": "Hotel Manager",
            "role": "manager"
        }
    }
    """
    return jsonify({
        'success': True,
        'user': {
            'id': current_user['id'],
            'username': current_user['username'],
            'full_name': current_user.get('full_name'),
            'role': current_user['role']
        }
    }), 200

# ============================================
# LOGOUT ENDPOINT (Client-side only)
# ============================================

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout endpoint (client should remove token)
    
    Response:
    {
        "success": true,
        "message": "Logged out successfully"
    }
    """
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200
