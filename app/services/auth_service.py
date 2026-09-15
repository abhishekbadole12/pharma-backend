import bcrypt
import secrets
from datetime import datetime, timezone
from bson import ObjectId
import app.extensions as extensions
from app.utils.helpers import utc_now


class AuthService:
    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password, password_hash):
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def create_user(data, role='CLIENT'):
        password_hash = AuthService.hash_password(data['password'])
        user = {
            'email': data['email'].lower().strip(),
            'phone': data.get('phone', '').strip(),
            'password_hash': password_hash,
            'role': role,
            'first_name': data.get('first_name', '').strip(),
            'last_name': data.get('last_name', '').strip(),
            'created_at': utc_now(),
            'updated_at': utc_now(),
        }
        if role == 'CLIENT':
            user['client_type'] = 'NORMAL'
            user['status'] = 'PENDING'
        else:
            user['status'] = 'APPROVED'
        result = extensions.db.users.insert_one(user)
        user['_id'] = result.inserted_id
        return user

    @staticmethod
    def authenticate(email, password):
        user = extensions.db.users.find_one({'email': email.lower().strip()})
        if not user:
            return None
        if not AuthService.verify_password(password, user['password_hash']):
            return None
        return user

    @staticmethod
    def create_reset_token(user_id):
        token = secrets.token_urlsafe(32)
        extensions.db.password_resets.update_one(
            {'user_id': ObjectId(user_id)},
            {'$set': {
                'token': token,
                'expires_at': datetime.now(timezone.utc).replace(
                    hour=datetime.now(timezone.utc).hour + 1
                ),
                'used': False,
            }},
            upsert=True
        )
        return token

    @staticmethod
    def verify_reset_token(token):
        reset = extensions.db.password_resets.find_one({'token': token, 'used': False})
        if not reset:
            return None
        if reset['expires_at'] < datetime.now(timezone.utc):
            return None
        return str(reset['user_id'])

    @staticmethod
    def reset_password(user_id, new_password):
        password_hash = AuthService.hash_password(new_password)
        extensions.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'password_hash': password_hash, 'updated_at': utc_now()}}
        )
        extensions.db.password_resets.update_one(
            {'user_id': ObjectId(user_id)},
            {'$set': {'used': True}}
        )
