from flask import Blueprint, request, jsonify, make_response, g, current_app
from marshmallow import ValidationError
from bson import ObjectId
from app.extensions import db, limiter
from app.middleware.auth import (
    generate_tokens, decode_token, login_required, admin_required, client_required
)
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.schemas.validation import SignupSchema, LoginSchema
from app.utils.helpers import serialize_doc, utc_now

auth_bp = Blueprint('auth', __name__)


def set_auth_cookies(response, access_token, refresh_token, remember=False):
    max_age = 604800 if remember else 3600
    secure = current_app.config.get('COOKIE_SECURE', False)
    samesite = current_app.config.get('COOKIE_SAMESITE', 'None')
    response.set_cookie(
        'access_token', access_token,
        httponly=True, secure=secure, samesite=samesite,
        max_age=max_age, path='/'
    )
    response.set_cookie(
        'refresh_token', refresh_token,
        httponly=True, secure=secure, samesite=samesite,
        max_age=604800, path='/'
    )
    return response


@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("5 per minute")
def signup():
    try:
        data = SignupSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    if data['password'] != data['confirm_password']:
        return jsonify({'error': 'Passwords do not match'}), 400

    if db.users.find_one({'email': data['email'].lower()}):
        return jsonify({'error': 'Email already registered'}), 409

    if db.users.find_one({'phone': data['phone']}):
        return jsonify({'error': 'Phone number already registered'}), 409

    user = AuthService.create_user(data)
    EmailService.send_admin_new_registration(user)
    NotificationService.notify_admins(
        'New Registration',
        f"New customer registration: {data['email']}",
        'info', '/admin/approvals'
    )

    return jsonify({
        'message': 'Registration successful. Please wait for admin approval.',
        'user': serialize_doc(user)
    }), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    try:
        data = LoginSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    user = AuthService.authenticate(data['email'], data['password'])
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401

    if user.get('role') == 'CLIENT' and user.get('status') == 'PENDING':
        return jsonify({'error': 'Your account is pending approval'}), 403
    if user.get('role') == 'CLIENT' and user.get('status') == 'REJECTED':
        return jsonify({'error': 'Your account registration was rejected'}), 403
    if user.get('role') == 'CLIENT' and user.get('status') == 'SUSPENDED':
        return jsonify({'error': 'Your account has been suspended'}), 403

    remember = request.get_json().get('remember_me', False)
    access_token, refresh_token = generate_tokens(str(user['_id']), user['role'])

    response = make_response(jsonify({
        'message': 'Login successful',
        'user': serialize_doc(user),
        'redirect': '/admin/dashboard' if user['role'] == 'ADMIN' else '/'
    }))
    return set_auth_cookies(response, access_token, refresh_token, remember)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({'message': 'Logged out successfully'}))
    response.set_cookie('access_token', '', expires=0, path='/')
    response.set_cookie('refresh_token', '', expires=0, path='/')
    return response


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 401

    payload = decode_token(refresh_token, 'refresh')
    if not payload:
        return jsonify({'error': 'Invalid refresh token'}), 401

    user = db.users.find_one({'_id': ObjectId(payload['sub'])})
    if not user:
        return jsonify({'error': 'User not found'}), 401

    access_token, new_refresh = generate_tokens(str(user['_id']), user['role'])
    response = make_response(jsonify({'message': 'Token refreshed'}))
    return set_auth_cookies(response, access_token, new_refresh)


@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    return jsonify({'user': serialize_doc(g.current_user)})


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    email = request.get_json().get('email', '').lower().strip()
    user = db.users.find_one({'email': email})
    if user:
        token = AuthService.create_reset_token(str(user['_id']))
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        EmailService.send_password_reset(email, name, token)
    return jsonify({'message': 'If the email exists, a reset link has been sent'})


@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    data = request.get_json()
    token = data.get('token')
    password = data.get('password')
    if not token or not password or len(password) < 8:
        return jsonify({'error': 'Invalid request'}), 400

    user_id = AuthService.verify_reset_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid or expired reset token'}), 400

    AuthService.reset_password(user_id, password)
    return jsonify({'message': 'Password reset successful'})
