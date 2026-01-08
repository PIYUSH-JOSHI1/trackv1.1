"""
Supabase Database Configuration for Track-V Traffic Management System
Handles all database operations, authentication, and real-time features
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import json

# Supabase Python Client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Warning: supabase-py not installed. Run: pip install supabase")


class SupabaseConfig:
    """Supabase configuration and client management"""
    
    def __init__(self):
        self.url = os.environ.get('SUPABASE_URL')
        self.anon_key = os.environ.get('SUPABASE_ANON_KEY')
        self.service_role_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        self.client: Optional[Client] = None
        self.admin_client: Optional[Client] = None
        
        if not all([self.url, self.anon_key]):
            print("Warning: Supabase credentials not configured")
            print("Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
        
    def get_client(self) -> Optional[Client]:
        """Get Supabase client for authenticated requests"""
        if not SUPABASE_AVAILABLE:
            return None
            
        if self.client is None and self.url and self.anon_key:
            self.client = create_client(self.url, self.anon_key)
        return self.client
    
    def get_admin_client(self) -> Optional[Client]:
        """Get Supabase admin client (service role) for backend operations"""
        if not SUPABASE_AVAILABLE:
            return None
            
        if self.admin_client is None and self.url and self.service_role_key:
            self.admin_client = create_client(self.url, self.service_role_key)
        return self.admin_client


# Global Supabase instance
supabase_config = SupabaseConfig()


class TrafficDataManager:
    """Manage traffic data storage and retrieval from Supabase"""
    
    def __init__(self):
        self.client = supabase_config.get_admin_client() or supabase_config.get_client()
        
    def save_traffic_data(self, junction_id: str, camera_index: int, data: Dict) -> bool:
        """
        Save real-time traffic data to Supabase
        
        Args:
            junction_id: UUID of the junction
            camera_index: Camera index (0-3)
            data: Traffic metrics dictionary
        """
        if not self.client:
            return False
            
        try:
            record = {
                'junction_id': junction_id,
                'camera_index': camera_index,
                'vehicle_count': data.get('total_count', 0),
                'car_count': data.get('car_count', 0),
                'truck_count': data.get('truck_count', 0),
                'bus_count': data.get('bus_count', 0),
                'bike_count': data.get('bike_count', 0),
                'congestion_level': data.get('congestion_level', 'low'),
                'signal_state': data.get('signal_state', 'RED'),
                'green_time_remaining': data.get('green_time', 0),
                'average_speed': data.get('average_speed'),
            }
            
            self.client.table('traffic_data').insert(record).execute()
            return True
            
        except Exception as e:
            print(f"Error saving traffic data: {e}")
            return False
    
    def get_latest_traffic_data(self, junction_id: str, camera_index: Optional[int] = None) -> List[Dict]:
        """Get latest traffic data for a junction"""
        if not self.client:
            return []
            
        try:
            query = self.client.table('traffic_data')\
                .select('*')\
                .eq('junction_id', junction_id)\
                .order('timestamp', desc=True)\
                .limit(10)
            
            if camera_index is not None:
                query = query.eq('camera_index', camera_index)
                
            result = query.execute()
            return result.data
            
        except Exception as e:
            print(f"Error fetching traffic data: {e}")
            return []
    
    def get_traffic_history(self, junction_id: str, hours: int = 24) -> List[Dict]:
        """Get traffic history for the past N hours"""
        if not self.client:
            return []
            
        try:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            result = self.client.table('traffic_data')\
                .select('*')\
                .eq('junction_id', junction_id)\
                .gte('timestamp', since)\
                .order('timestamp', desc=True)\
                .execute()
                
            return result.data
            
        except Exception as e:
            print(f"Error fetching traffic history: {e}")
            return []


class JunctionManager:
    """Manage junction data in Supabase"""
    
    def __init__(self):
        self.client = supabase_config.get_admin_client() or supabase_config.get_client()
        
    def get_all_junctions(self) -> List[Dict]:
        """Get all junctions with their details"""
        if not self.client:
            return []
            
        try:
            result = self.client.table('junctions')\
                .select('*, cameras(*)')\
                .eq('status', 'active')\
                .execute()
            return result.data
            
        except Exception as e:
            print(f"Error fetching junctions: {e}")
            return []
    
    def get_junction_by_id(self, junction_id: str) -> Optional[Dict]:
        """Get a specific junction"""
        if not self.client:
            return None
            
        try:
            result = self.client.table('junctions')\
                .select('*, cameras(*)')\
                .eq('id', junction_id)\
                .single()\
                .execute()
            return result.data
            
        except Exception as e:
            print(f"Error fetching junction: {e}")
            return None
    
    def update_camera_source(self, junction_id: str, camera_index: int, 
                             source_type: str, source_url: str) -> bool:
        """Update camera video source"""
        if not self.client:
            return False
            
        try:
            self.client.table('cameras')\
                .update({
                    'source_type': source_type,
                    'source_url': source_url,
                    'is_active': True,
                    'last_active': datetime.utcnow().isoformat()
                })\
                .eq('junction_id', junction_id)\
                .eq('camera_index', camera_index)\
                .execute()
            return True
            
        except Exception as e:
            print(f"Error updating camera: {e}")
            return False


class AlertManager:
    """Manage traffic alerts and email notifications"""
    
    def __init__(self):
        self.client = supabase_config.get_admin_client() or supabase_config.get_client()
        
    def create_alert(self, junction_id: str, alert_data: Dict, user_id: Optional[str] = None) -> Optional[str]:
        """
        Create a new traffic alert
        
        Args:
            junction_id: Junction UUID
            alert_data: Alert details (type, severity, title, description, camera_index)
            user_id: ID of user creating the alert
            
        Returns:
            Alert ID if successful
        """
        if not self.client:
            return None
            
        try:
            # Get junction to find inspector email
            junction = self.client.table('junctions')\
                .select('inspector_email, inspector_name')\
                .eq('id', junction_id)\
                .single()\
                .execute()
            
            inspector_email = junction.data.get('inspector_email') if junction.data else None
            
            record = {
                'junction_id': junction_id,
                'camera_index': alert_data.get('camera_index'),
                'alert_type': alert_data.get('type', 'manual'),
                'severity': alert_data.get('severity', 'medium'),
                'title': alert_data.get('title', 'Traffic Alert'),
                'description': alert_data.get('description', ''),
                'sent_to_email': inspector_email,
                'created_by': user_id,
            }
            
            result = self.client.table('alerts').insert(record).execute()
            
            if result.data:
                return result.data[0].get('id')
            return None
            
        except Exception as e:
            print(f"Error creating alert: {e}")
            return None
    
    def mark_email_sent(self, alert_id: str) -> bool:
        """Mark alert email as sent"""
        if not self.client:
            return False
            
        try:
            self.client.table('alerts')\
                .update({
                    'email_sent': True,
                    'email_sent_at': datetime.utcnow().isoformat()
                })\
                .eq('id', alert_id)\
                .execute()
            return True
            
        except Exception as e:
            print(f"Error updating alert: {e}")
            return False
    
    def get_pending_alerts(self) -> List[Dict]:
        """Get alerts that need email sending"""
        if not self.client:
            return []
            
        try:
            result = self.client.table('alerts')\
                .select('*, junctions(name, inspector_email, inspector_name)')\
                .eq('email_sent', False)\
                .not_.is_('sent_to_email', 'null')\
                .execute()
            return result.data
            
        except Exception as e:
            print(f"Error fetching pending alerts: {e}")
            return []
    
    def get_junction_alerts(self, junction_id: str, limit: int = 50) -> List[Dict]:
        """Get alerts for a specific junction"""
        if not self.client:
            return []
            
        try:
            result = self.client.table('alerts')\
                .select('*')\
                .eq('junction_id', junction_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            return result.data
            
        except Exception as e:
            print(f"Error fetching alerts: {e}")
            return []


class UserProfileManager:
    """Manage user profiles in Supabase"""
    
    def __init__(self):
        self.client = supabase_config.get_client()
        
    def get_profile(self, user_id: str) -> Optional[Dict]:
        """Get user profile"""
        if not self.client:
            return None
            
        try:
            result = self.client.table('profiles')\
                .select('*')\
                .eq('id', user_id)\
                .single()\
                .execute()
            return result.data
            
        except Exception as e:
            print(f"Error fetching profile: {e}")
            return None
    
    def update_profile(self, user_id: str, updates: Dict) -> bool:
        """
        Update user profile
        
        Args:
            user_id: User UUID
            updates: Fields to update (full_name, badge_number, phone, etc.)
        """
        if not self.client:
            return False
            
        # Only allow specific fields to be updated
        allowed_fields = ['full_name', 'badge_number', 'phone', 'department', 
                         'avatar_url', 'email_alerts_enabled', 'dark_mode']
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not safe_updates:
            return False
            
        try:
            self.client.table('profiles')\
                .update(safe_updates)\
                .eq('id', user_id)\
                .execute()
            return True
            
        except Exception as e:
            print(f"Error updating profile: {e}")
            return False
    
    def get_user_settings(self, user_id: str) -> Dict:
        """Get user settings (dark mode, email alerts)"""
        profile = self.get_profile(user_id)
        if profile:
            return {
                'dark_mode': profile.get('dark_mode', False),
                'email_alerts_enabled': profile.get('email_alerts_enabled', True)
            }
        return {'dark_mode': False, 'email_alerts_enabled': True}


class ReportManager:
    """Manage traffic reports"""
    
    def __init__(self):
        self.client = supabase_config.get_admin_client() or supabase_config.get_client()
        
    def generate_hourly_report(self, junction_id: str) -> Optional[Dict]:
        """Generate hourly traffic report from aggregated data"""
        if not self.client:
            return None
            
        try:
            # Get traffic data for the past hour
            one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            
            result = self.client.table('traffic_data')\
                .select('*')\
                .eq('junction_id', junction_id)\
                .gte('timestamp', one_hour_ago)\
                .execute()
            
            if not result.data:
                return None
            
            # Aggregate data
            total_vehicles = sum(d.get('vehicle_count', 0) for d in result.data)
            total_cars = sum(d.get('car_count', 0) for d in result.data)
            total_trucks = sum(d.get('truck_count', 0) for d in result.data)
            total_buses = sum(d.get('bus_count', 0) for d in result.data)
            total_bikes = sum(d.get('bike_count', 0) for d in result.data)
            
            report = {
                'junction_id': junction_id,
                'report_type': 'hourly',
                'report_date': datetime.utcnow().date().isoformat(),
                'report_hour': datetime.utcnow().hour,
                'total_vehicles': total_vehicles,
                'car_percentage': (total_cars / total_vehicles * 100) if total_vehicles > 0 else 0,
                'truck_percentage': (total_trucks / total_vehicles * 100) if total_vehicles > 0 else 0,
                'bus_percentage': (total_buses / total_vehicles * 100) if total_vehicles > 0 else 0,
                'bike_percentage': (total_bikes / total_vehicles * 100) if total_vehicles > 0 else 0,
                'report_data': json.dumps({
                    'raw_count': len(result.data),
                    'peak_count': max(d.get('vehicle_count', 0) for d in result.data)
                })
            }
            
            # Save report
            self.client.table('traffic_reports').upsert(report).execute()
            
            return report
            
        except Exception as e:
            print(f"Error generating report: {e}")
            return None
    
    def get_reports(self, junction_id: str, report_type: str = 'hourly', 
                   days: int = 7) -> List[Dict]:
        """Get traffic reports"""
        if not self.client:
            return []
            
        try:
            since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
            
            result = self.client.table('traffic_reports')\
                .select('*')\
                .eq('junction_id', junction_id)\
                .eq('report_type', report_type)\
                .gte('report_date', since)\
                .order('report_date', desc=True)\
                .execute()
                
            return result.data
            
        except Exception as e:
            print(f"Error fetching reports: {e}")
            return []


# Export managers for use in Flask app
traffic_data_manager = TrafficDataManager()
junction_manager = JunctionManager()
alert_manager = AlertManager()
profile_manager = UserProfileManager()
report_manager = ReportManager()
