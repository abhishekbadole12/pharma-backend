import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _send(to_email, subject, html_body):
        config = current_app.config
        if not config.get('SMTP_USERNAME') or not config.get('SMTP_PASSWORD'):
            logger.warning(f"SMTP not configured. Would send email to {to_email}: {subject}")
            return True
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = config['SMTP_FROM']
            msg['To'] = to_email
            msg.attach(MIMEText(html_body, 'html'))
            with smtplib.SMTP(config['SMTP_HOST'], config['SMTP_PORT']) as server:
                server.starttls()
                server.login(config['SMTP_USERNAME'], config['SMTP_PASSWORD'])
                server.sendmail(config['SMTP_FROM'], to_email, msg.as_string())
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_admin_new_registration(client):
        admin_email = current_app.config['ADMIN_NOTIFICATION_EMAIL']
        name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2>New Client Registration</h2>
        <p>A new client has registered and requires approval.</p>
        <table style="border-collapse:collapse;">
        <tr><td style="padding:8px;font-weight:bold;">Name:</td><td style="padding:8px;">{name}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Email:</td><td style="padding:8px;">{client.get('email')}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Phone:</td><td style="padding:8px;">{client.get('phone')}</td></tr>
        <tr><td style="padding:8px;font-weight:bold;">Type:</td><td style="padding:8px;">{client.get('client_type')}</td></tr>
        </table>
        <p>Please log in to the admin dashboard to review and approve this registration.</p>
        </body></html>
        """
        return EmailService._send(admin_email, 'New Client Registration - Approval Required', html)

    @staticmethod
    def send_client_approved(email, name):
        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2>Account Approved!</h2>
        <p>Dear {name},</p>
        <p>Your account has been approved. You can now login and start shopping.</p>
        <p><a href="{current_app.config['FRONTEND_URL']}/login">Login Now</a></p>
        </body></html>
        """
        return EmailService._send(email, 'Your Account Has Been Approved', html)

    @staticmethod
    def send_client_rejected(email, name, reason=''):
        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2>Account Registration Update</h2>
        <p>Dear {name},</p>
        <p>We regret to inform you that your registration has been rejected.</p>
        {f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''}
        <p>Please contact support if you have questions.</p>
        </body></html>
        """
        return EmailService._send(email, 'Registration Status Update', html)

    @staticmethod
    def send_order_confirmation(email, name, order):
        items_html = ''.join([
            f"<tr><td style='padding:8px;'>{item.get('name')}</td>"
            f"<td style='padding:8px;'>{item.get('quantity')}</td></tr>"
            for item in order.get('items', [])
        ])
        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2>Order Confirmation</h2>
        <p>Dear {name},</p>
        <p>Your order <strong>#{order.get('order_number')}</strong> has been placed successfully.</p>
        <table style="border-collapse:collapse;width:100%;">
        <tr style="background:#f5f5f5;"><th style="padding:8px;text-align:left;">Product</th>
        <th style="padding:8px;">Qty</th></tr>
        {items_html}
        </table>
        <p>Thank you for shopping with us!</p>
        </body></html>
        """
        return EmailService._send(email, f'Order Confirmation - #{order.get("order_number")}', html)

    @staticmethod
    def send_order_status_update(email, name, order, new_status):
        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2>Order Status Update</h2>
        <p>Dear {name},</p>
        <p>Your order <strong>#{order.get('order_number')}</strong> status has been updated to: 
        <strong>{new_status.replace('_', ' ').title()}</strong></p>
        <p>Thank you for shopping with us!</p>
        </body></html>
        """
        return EmailService._send(email, f'Order #{order.get("order_number")} - Status Update', html)

    @staticmethod
    def send_password_reset(email, name, reset_token):
        reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password?token={reset_token}"
        html = f"""
        <html><body style="font-family:Arial,sans-serif;">
        <h2>Password Reset</h2>
        <p>Dear {name},</p>
        <p>Click the link below to reset your password:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>This link expires in 1 hour.</p>
        </body></html>
        """
        return EmailService._send(email, 'Password Reset Request', html)
