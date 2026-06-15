from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from routes.predict import predict_bp
from utils.prediction import load_artifacts


# Load environment variables
load_dotenv()

# Import routes
from routes.auth import auth_bp
from routes.upload import upload_bp
from routes.dashboard import dashboard_bp

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB upload

# Enable CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(upload_bp, url_prefix='/api')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(predict_bp) 

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Hotel Electricity Dashboard API is running'
    }), 200

# Root endpoint
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'name': 'Hotel Electricity Dashboard API',
        'version': '1.0.0',
        'endpoints': {
            'auth': '/api/auth/*',
            'upload': '/api/datasets/*',
            'dashboard': '/api/dashboard/*'
        }
    }), 200

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large. Maximum size is 16MB'}), 413

if __name__ == '__main__':
    port  = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'

    print(f"\n🚀 Server starting on http://localhost:{port}")
    print(f"📊 Dashboard API ready\n")

    load_artifacts()
    app.run(host='0.0.0.0', port=port, debug=debug)
    