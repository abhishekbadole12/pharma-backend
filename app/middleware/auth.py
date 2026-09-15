import jwt
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from app.extensions import db
from bson import ObjectId


def generate_tokens(user_id, role):
    now = datetime.now(timezone.utc)
    access_expires = current_app.config.get('JWT_ACCESS_EXPIRES', 3600)
    refresh_expires = current_app.config.get('JWT_REFRESH_EXPIRES', 604800)
    access_payload = {
        'sub': str(user_id),
        'role': role,
        'type': 'access',
        'iat': now,
        'exp': now + timedelta(seconds=access_expires),
    }
    refresh_payload = {
        'sub': str(user_id),
        'role': role,
        'type': 'refresh',
        'iat': now,
        'exp': now + timedelta(seconds=refresh_expires),
    }
    access_token = jwt.encode(access_payload, current_app.config['JWT_SECRET'], algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, current_app.config['JWT_REFRESH_SECRET'], algorithm='HS256')
    return access_token, refresh_token


def decode_token(token, token_type='access'):
    secret = current_app.config['JWT_SECRET'] if token_type == 'access' else current_app.config['JWT_REFRESH_SECRET']
    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        if payload.get('type') != token_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_from_request():
    token = request.cookies.get('access_token')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
    return token


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        payload = decode_token(token, 'access')
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        user = db.users.find_one({'_id': ObjectId(payload['sub'])})
        if not user:
            return jsonify({'error': 'User not found'}), 401
        g.current_user = user
        g.user_id = str(user['_id'])
        g.user_role = user.get('role')
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.user_role != 'ADMIN':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def client_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.user_role != 'CLIENT':
            return jsonify({'error': 'Client access required'}), 403
        if g.current_user.get('status') != 'APPROVED':
            return jsonify({'error': 'Account not approved. Please wait for admin approval.'}), 403
        return f(*args, **kwargs)
    return decorated


def approved_client_required(f):
    @wraps(f)
    @client_required
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated
