import os
from datetime import timedelta
from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/pharma_ecommerce')
    MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'pharma_ecommerce')
    JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-secret-key')
    JWT_REFRESH_SECRET = os.environ.get('JWT_REFRESH_SECRET', 'jwt-refresh-secret')
    JWT_ACCESS_EXPIRES = int(os.environ.get('JWT_ACCESS_EXPIRES', 3600))
    JWT_REFRESH_EXPIRES = int(os.environ.get('JWT_REFRESH_EXPIRES', 604800))
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    UPLOAD_DIR = os.environ.get(
        'UPLOAD_DIR',
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
    )
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 'local')  # 'local' or 's3'
    S3_BUCKET = os.environ.get('S3_BUCKET', '')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 5242880))
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@123456')
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_FROM = os.environ.get('SMTP_FROM', 'noreply@pharmaecommerce.com')
    ADMIN_NOTIFICATION_EMAIL = os.environ.get('ADMIN_NOTIFICATION_EMAIL', 'admin@example.com')
    COOKIE_SECURE = os.environ.get('COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')
    COOKIE_SAMESITE = os.environ.get('COOKIE_SAMESITE', 'Lax' if os.environ.get('FLASK_ENV') != 'production' else 'Strict')

    @property
    def access_token_expires(self):
        return timedelta(seconds=self.JWT_ACCESS_EXPIRES)

    @property
    def refresh_token_expires(self):
        return timedelta(seconds=self.JWT_REFRESH_EXPIRES)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
