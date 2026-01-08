"""
Supabase API Routes for Track-V Traffic Management System
Add these routes to app.py for full Supabase integration
"""

from flask import Blueprint, request, jsonify
import os

# Import Supabase managers
from supabase_config import (
    traffic_data_manager,
    junction_manager,
    alert_manager,
    profile_manager,
    report_manager,
    supabase_config
)
from email_service import email_service

# Create Blueprint for Supabase routes
supabase_bp = Blueprint('supabase', __name__, url_prefix='/api/v1')


# =============================================
# AUTHENTICATION ENDPOINTS
# =============================================

@supabase_bp.route('/auth/signup', methods=['POST'])
def signup():
    """Register new user"""
    client = supabase_config.get_client()
    if not client:
        return jsonify({'error': 'Database not configured'}), 503
    
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        full_name = data.get('full_name', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Sign up with Supabase Auth
        result = client.auth.sign_up({
            'email': email,
            'password': password,
            'options': {
                'data': {
                    'full_name': full_name
                }
            }
        })
        
        if result.user:
            return jsonify({
                'success': True,
                'user': {
                    'id': result.user.id,
                    'email': result.user.email
                },
                'message': 'Account created successfully'
            })
        
        return jsonify({'error': 'Registration failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@supabase_bp.route('/auth/login', methods=['POST'])
def login():
    """User login"""
    client = supabase_config.get_client()
    if not client:
        return jsonify({'error': 'Database not configured'}), 503
    
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Sign in with Supabase Auth
        result = client.auth.sign_in_with_password({
            'email': email,
            'password': password
        })
        
        if result.user and result.session:
            # Get user profile
            profile = profile_manager.get_profile(result.user.id)
            
            return jsonify({
                'success': True,
                'user': {
                    'id': result.user.id,
                    'email': result.user.email,
                    'profile': profile
                },
                'session': {
                    'access_token': result.session.access_token,
                    'refresh_token': result.session.refresh_token,
                    'expires_at': result.session.expires_at
                }
            })
        
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@supabase_bp.route('/auth/logout', methods=['POST'])
def logout():
    """User logout"""
    client = supabase_config.get_client()
    if not client:
        return jsonify({'error': 'Database not configured'}), 503
    
    try:
        client.auth.sign_out()
        return jsonify({'success': True, 'message': 'Logged out successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================
# USER PROFILE ENDPOINTS
# =============================================

@supabase_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get current user's profile"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 401
    
    profile = profile_manager.get_profile(user_id)
    if profile:
        return jsonify({'success': True, 'profile': profile})
    return jsonify({'error': 'Profile not found'}), 404


@supabase_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 401
    
    try:
        updates = request.json
        success = profile_manager.update_profile(user_id, updates)
        
        if success:
            profile = profile_manager.get_profile(user_id)
            return jsonify({'success': True, 'profile': profile})
        return jsonify({'error': 'Update failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@supabase_bp.route('/profile/settings', methods=['GET'])
def get_settings():
    """Get user settings (dark mode, email alerts)"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 401
    
    settings = profile_manager.get_user_settings(user_id)
    return jsonify({'success': True, 'settings': settings})


@supabase_bp.route('/profile/settings', methods=['PUT'])
def update_settings():
    """Update user settings"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 401
    
    try:
        settings = request.json
        allowed = ['dark_mode', 'email_alerts_enabled']
        updates = {k: v for k, v in settings.items() if k in allowed}
        
        success = profile_manager.update_profile(user_id, updates)
        if success:
            return jsonify({'success': True, 'settings': profile_manager.get_user_settings(user_id)})
        return jsonify({'error': 'Update failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================
# JUNCTION ENDPOINTS
# =============================================

@supabase_bp.route('/junctions', methods=['GET'])
def get_junctions():
    """Get all junctions with cameras"""
    junctions = junction_manager.get_all_junctions()
    return jsonify({'success': True, 'junctions': junctions})


@supabase_bp.route('/junctions/<junction_id>', methods=['GET'])
def get_junction(junction_id):
    """Get specific junction"""
    junction = junction_manager.get_junction_by_id(junction_id)
    if junction:
        return jsonify({'success': True, 'junction': junction})
    return jsonify({'error': 'Junction not found'}), 404


@supabase_bp.route('/junctions/<junction_id>/cameras/<int:camera_index>', methods=['PUT'])
def update_camera_source(junction_id, camera_index):
    """Update camera video source"""
    try:
        data = request.json
        source_type = data.get('source_type')  # video_file, youtube, rtsp, http_stream
        source_url = data.get('source_url')
        
        if not source_type or not source_url:
            return jsonify({'error': 'source_type and source_url required'}), 400
        
        success = junction_manager.update_camera_source(
            junction_id, camera_index, source_type, source_url
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Camera source updated'})
        return jsonify({'error': 'Update failed'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================
# TRAFFIC DATA ENDPOINTS
# =============================================

@supabase_bp.route('/traffic/<junction_id>', methods=['GET'])
def get_traffic_data(junction_id):
    """Get latest traffic data for junction"""
    camera_index = request.args.get('camera', type=int)
    data = traffic_data_manager.get_latest_traffic_data(junction_id, camera_index)
    return jsonify({'success': True, 'data': data})


@supabase_bp.route('/traffic/<junction_id>/history', methods=['GET'])
def get_traffic_history(junction_id):
    """Get traffic history"""
    hours = request.args.get('hours', default=24, type=int)
    data = traffic_data_manager.get_traffic_history(junction_id, hours)
    return jsonify({'success': True, 'data': data})


@supabase_bp.route('/traffic/<junction_id>', methods=['POST'])
def save_traffic_data(junction_id):
    """Save traffic data (called by backend processor)"""
    try:
        data = request.json
        camera_index = data.get('camera_index', 0)
        
        success = traffic_data_manager.save_traffic_data(junction_id, camera_index, data)
        
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to save data'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================
# ALERT ENDPOINTS
# =============================================

@supabase_bp.route('/alerts', methods=['POST'])
def create_alert():
    """Create traffic alert and send email"""
    try:
        data = request.json
        junction_id = data.get('junction_id')
        user_id = request.headers.get('X-User-ID')
        
        if not junction_id:
            return jsonify({'error': 'junction_id required'}), 400
        
        alert_data = {
            'type': data.get('type', 'manual'),
            'severity': data.get('severity', 'medium'),
            'title': data.get('title', 'Traffic Alert'),
            'description': data.get('description', ''),
            'camera_index': data.get('camera_index')
        }
        
        # Create alert in database
        alert_id = alert_manager.create_alert(junction_id, alert_data, user_id)
        
        if alert_id:
            # Get junction info for email
            junction = junction_manager.get_junction_by_id(junction_id)
            
            if junction and junction.get('inspector_email'):
                # Check if user has email alerts enabled
                should_send_email = True
                if user_id:
                    settings = profile_manager.get_user_settings(user_id)
                    should_send_email = settings.get('email_alerts_enabled', True)
                
                if should_send_email:
                    # Send email asynchronously
                    email_service.send_alert_async(
                        to_email=junction.get('inspector_email'),
                        inspector_name=junction.get('inspector_name', 'Inspector'),
                        junction_name=junction.get('name', 'Unknown Junction'),
                        alert_data=alert_data
                    )
                    
                    # Mark email as sent
                    alert_manager.mark_email_sent(alert_id)
            
            return jsonify({
                'success': True,
                'alert_id': alert_id,
                'message': 'Alert created and email sent'
            })
        
        return jsonify({'error': 'Failed to create alert'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@supabase_bp.route('/alerts/junction/<junction_id>', methods=['GET'])
def get_junction_alerts(junction_id):
    """Get alerts for a junction"""
    limit = request.args.get('limit', default=50, type=int)
    alerts = alert_manager.get_junction_alerts(junction_id, limit)
    return jsonify({'success': True, 'alerts': alerts})


@supabase_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    client = supabase_config.get_client()
    if not client:
        return jsonify({'error': 'Database not configured'}), 503
    
    try:
        user_id = request.headers.get('X-User-ID')
        
        client.table('alerts').update({
            'acknowledged': True,
            'acknowledged_by': user_id,
            'acknowledged_at': 'now()'
        }).eq('id', alert_id).execute()
        
        return jsonify({'success': True, 'message': 'Alert acknowledged'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================
# REPORT ENDPOINTS
# =============================================

@supabase_bp.route('/reports/<junction_id>/generate', methods=['POST'])
def generate_report(junction_id):
    """Generate hourly report"""
    report = report_manager.generate_hourly_report(junction_id)
    if report:
        return jsonify({'success': True, 'report': report})
    return jsonify({'error': 'Failed to generate report'}), 500


@supabase_bp.route('/reports/<junction_id>', methods=['GET'])
def get_reports(junction_id):
    """Get traffic reports"""
    report_type = request.args.get('type', default='hourly')
    days = request.args.get('days', default=7, type=int)
    
    reports = report_manager.get_reports(junction_id, report_type, days)
    return jsonify({'success': True, 'reports': reports})


@supabase_bp.route('/reports/<junction_id>/download', methods=['GET'])
def download_report(junction_id):
    """Download report as CSV"""
    import csv
    from io import StringIO
    from flask import Response
    
    report_type = request.args.get('type', default='daily')
    days = request.args.get('days', default=30, type=int)
    
    reports = report_manager.get_reports(junction_id, report_type, days)
    
    if not reports:
        return jsonify({'error': 'No reports found'}), 404
    
    # Create CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=reports[0].keys())
    writer.writeheader()
    writer.writerows(reports)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=traffic_report_{junction_id}.csv'}
    )


# =============================================
# MAP DATA ENDPOINT
# =============================================

@supabase_bp.route('/map/data', methods=['GET'])
def get_map_data():
    """Get all junctions with their latest traffic data for map view"""
    junctions = junction_manager.get_all_junctions()
    
    map_data = []
    for junction in junctions:
        junction_data = {
            'id': junction.get('id'),
            'name': junction.get('name'),
            'location_name': junction.get('location_name'),
            'latitude': float(junction.get('latitude', 0)),
            'longitude': float(junction.get('longitude', 0)),
            'status': junction.get('status'),
            'inspector_name': junction.get('inspector_name'),
            'cameras': []
        }
        
        # Get latest traffic data for each camera
        cameras = junction.get('cameras', [])
        for camera in cameras:
            camera_index = camera.get('camera_index')
            latest_data = traffic_data_manager.get_latest_traffic_data(
                junction.get('id'), camera_index
            )
            
            camera_data = {
                'index': camera_index,
                'name': camera.get('name'),
                'source_type': camera.get('source_type'),
                'is_active': camera.get('is_active', False),
                'traffic': latest_data[0] if latest_data else None
            }
            junction_data['cameras'].append(camera_data)
        
        map_data.append(junction_data)
    
    return jsonify({'success': True, 'data': map_data})


# =============================================
# AVATAR UPLOAD ENDPOINT
# =============================================

@supabase_bp.route('/profile/avatar', methods=['POST'])
def upload_avatar():
    """Upload profile avatar to Supabase Storage"""
    user_id = request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_types = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if ext not in allowed_types:
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        client = supabase_config.get_client()
        if not client:
            return jsonify({'error': 'Storage not configured'}), 503
        
        # Upload to Supabase Storage
        filename = f"avatars/{user_id}.{ext}"
        file_bytes = file.read()
        
        # Upload file
        result = client.storage.from_('avatars').upload(
            filename,
            file_bytes,
            {'upsert': 'true'}
        )
        
        # Get public URL
        public_url = client.storage.from_('avatars').get_public_url(filename)
        
        # Update profile with avatar URL
        profile_manager.update_profile(user_id, {'avatar_url': public_url})
        
        return jsonify({
            'success': True,
            'avatar_url': public_url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Function to register blueprint with Flask app
def register_supabase_routes(app):
    """Register Supabase routes with Flask app"""
    app.register_blueprint(supabase_bp)
    print("Supabase API routes registered at /api/v1/")
