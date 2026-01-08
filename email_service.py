"""
Email Alert Service for Track-V Traffic Management System
Handles sending email notifications to junction inspectors
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from typing import Optional, Dict
import threading


class EmailAlertService:
    """
    Email service for sending traffic alerts to inspectors
    Uses SMTP (Gmail, Outlook, or custom SMTP server)
    """
    
    def __init__(self):
        # Email configuration from environment variables
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.sender_email = os.environ.get('SMTP_EMAIL')
        self.sender_password = os.environ.get('SMTP_PASSWORD')  # App password for Gmail
        self.sender_name = os.environ.get('SMTP_SENDER_NAME', 'Track-V Traffic System')
        
        self.is_configured = all([self.sender_email, self.sender_password])
        
        if not self.is_configured:
            print("Warning: Email service not configured. Set SMTP_EMAIL and SMTP_PASSWORD")
    
    def send_alert_email(self, 
                         to_email: str, 
                         inspector_name: str,
                         junction_name: str,
                         alert_data: Dict) -> bool:
        """
        Send traffic alert email to inspector
        
        Args:
            to_email: Inspector's email address
            inspector_name: Inspector's name
            junction_name: Name of the junction
            alert_data: Alert details (type, severity, title, description, camera_index)
            
        Returns:
            True if email sent successfully
        """
        if not self.is_configured:
            print(f"Email not configured. Would send to: {to_email}")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 Traffic Alert - {junction_name} - {alert_data.get('severity', 'medium').upper()}"
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            
            # Alert details
            alert_type = alert_data.get('type', 'manual')
            severity = alert_data.get('severity', 'medium')
            title = alert_data.get('title', 'Traffic Alert')
            description = alert_data.get('description', 'No additional details provided.')
            camera_index = alert_data.get('camera_index', 'N/A')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Severity colors
            severity_colors = {
                'low': '#28a745',      # Green
                'medium': '#ffc107',   # Yellow
                'high': '#fd7e14',     # Orange
                'critical': '#dc3545'  # Red
            }
            severity_color = severity_colors.get(severity, '#6c757d')
            
            # HTML email template
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                    .header h1 {{ margin: 0; font-size: 24px; }}
                    .alert-badge {{ display: inline-block; background: {severity_color}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; margin-top: 10px; text-transform: uppercase; }}
                    .content {{ padding: 30px; }}
                    .info-box {{ background: #f8f9fa; border-left: 4px solid {severity_color}; padding: 15px; margin: 20px 0; border-radius: 0 5px 5px 0; }}
                    .info-row {{ display: flex; margin: 10px 0; }}
                    .info-label {{ font-weight: bold; color: #666; width: 120px; }}
                    .info-value {{ color: #333; }}
                    .description {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                    .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 30px; border-radius: 5px; text-decoration: none; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🚦 Track-V Traffic Alert</h1>
                        <div class="alert-badge">{severity} Severity</div>
                    </div>
                    <div class="content">
                        <p>Dear <strong>{inspector_name}</strong>,</p>
                        <p>A traffic alert has been generated for your assigned junction.</p>
                        
                        <div class="info-box">
                            <div class="info-row">
                                <span class="info-label">Junction:</span>
                                <span class="info-value">{junction_name}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Camera:</span>
                                <span class="info-value">Camera {camera_index}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Alert Type:</span>
                                <span class="info-value">{alert_type.replace('_', ' ').title()}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Time:</span>
                                <span class="info-value">{timestamp}</span>
                            </div>
                        </div>
                        
                        <h3>{title}</h3>
                        <div class="description">
                            <p>{description}</p>
                        </div>
                        
                        <p>Please take appropriate action as needed.</p>
                        
                        <center>
                            <a href="#" class="btn">View Dashboard</a>
                        </center>
                    </div>
                    <div class="footer">
                        <p>This is an automated message from Track-V Traffic Management System.</p>
                        <p>© 2026 Track-V. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text version
            text_body = f"""
            Track-V Traffic Alert
            =====================
            
            Dear {inspector_name},
            
            A traffic alert has been generated for your assigned junction.
            
            Details:
            - Junction: {junction_name}
            - Camera: Camera {camera_index}
            - Alert Type: {alert_type.replace('_', ' ').title()}
            - Severity: {severity.upper()}
            - Time: {timestamp}
            
            Title: {title}
            
            Description: {description}
            
            Please take appropriate action as needed.
            
            --
            Track-V Traffic Management System
            """
            
            # Attach parts
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"Alert email sent to {to_email}")
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def send_alert_async(self, to_email: str, inspector_name: str,
                        junction_name: str, alert_data: Dict) -> None:
        """Send alert email in background thread"""
        thread = threading.Thread(
            target=self.send_alert_email,
            args=(to_email, inspector_name, junction_name, alert_data)
        )
        thread.daemon = True
        thread.start()
    
    def send_daily_report(self, to_email: str, inspector_name: str,
                         junction_name: str, report_data: Dict) -> bool:
        """Send daily traffic report email"""
        if not self.is_configured:
            return False
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📊 Daily Traffic Report - {junction_name} - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = to_email
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
                    .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; text-align: center; }}
                    .content {{ padding: 30px; }}
                    .stat-box {{ display: inline-block; background: #f8f9fa; padding: 20px; margin: 10px; border-radius: 10px; text-align: center; min-width: 120px; }}
                    .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; }}
                    .stat-label {{ color: #666; font-size: 14px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📊 Daily Traffic Report</h1>
                        <p>{junction_name}</p>
                    </div>
                    <div class="content">
                        <p>Dear {inspector_name},</p>
                        <p>Here is your daily traffic summary:</p>
                        
                        <center>
                            <div class="stat-box">
                                <div class="stat-number">{report_data.get('total_vehicles', 0)}</div>
                                <div class="stat-label">Total Vehicles</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-number">{report_data.get('peak_hour', 'N/A')}</div>
                                <div class="stat-label">Peak Hour</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-number">{report_data.get('avg_congestion', 'Low')}</div>
                                <div class="stat-label">Avg Congestion</div>
                            </div>
                        </center>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"Error sending report email: {e}")
            return False


# Global email service instance
email_service = EmailAlertService()
