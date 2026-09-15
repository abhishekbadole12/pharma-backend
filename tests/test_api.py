def test_health(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('status') == 'healthy'


def test_list_categories(client):
    res = client.get('/api/categories')
    assert res.status_code == 200
    data = res.get_json()
    assert 'categories' in data
import pytest
from app import create_app
import app.extensions as extensions
from app.services.auth_service import AuthService


@pytest.fixture
def app():
    app = create_app('development')
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    user = AuthService.create_user({
        'email': 'testadmin@test.com',
        'password': 'Admin@123456',
        'first_name': 'Test', 'last_name': 'Admin',
        'phone': '1111111111',
    }, role='ADMIN')
    return user


@pytest.fixture
def approved_client(app):
    user = AuthService.create_user({
        'email': 'testclient@test.com',
        'password': 'Client@123',
        'first_name': 'Test', 'last_name': 'Client',
        'phone': '2222222222',
        'address': 'Test St', 'city': 'Test', 'state': 'Test', 'pincode': '123456',
    })
    extensions.db.users.update_one({'_id': user['_id']}, {'$set': {'status': 'APPROVED'}})
    return user


class TestHealth:
    def test_health_check(self, client):
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.json['status'] == 'healthy'


class TestAuth:
    def test_signup(self, client):
        response = client.post('/api/auth/signup', json={
            'email': 'newuser@test.com',
            'phone': '3333333333',
            'password': 'Test@1234',
            'confirm_password': 'Test@1234',
            'client_type': 'NORMAL',
            'first_name': 'New', 'last_name': 'User',
            'address': '123 St', 'city': 'City', 'state': 'State', 'pincode': '400001',
        })
        assert response.status_code == 201

    def test_signup_duplicate_email(self, client, approved_client):
        response = client.post('/api/auth/signup', json={
            'email': 'testclient@test.com',
            'phone': '4444444444',
            'password': 'Test@1234',
            'confirm_password': 'Test@1234',
            'first_name': 'Dup', 'last_name': 'User',
            'address': '123 St', 'city': 'City', 'state': 'State', 'pincode': '400001',
        })
        assert response.status_code == 409

    def test_login_admin(self, client, admin_user):
        response = client.post('/api/auth/login', json={
            'email': 'testadmin@test.com',
            'password': 'Admin@123456',
        })
        assert response.status_code == 200
        assert 'access_token' in response.headers.get('Set-Cookie', '') or response.json.get('user')

    def test_login_invalid(self, client):
        response = client.post('/api/auth/login', json={
            'email': 'wrong@test.com',
            'password': 'wrongpassword',
        })
        assert response.status_code == 401

    def test_pending_client_cannot_login(self, client, app):
        user = AuthService.create_user({
            'email': 'pending@test.com', 'password': 'Test@1234',
            'first_name': 'Pending', 'last_name': 'User',
            'phone': '5555555555',
            'address': 'St', 'city': 'C', 'state': 'S', 'pincode': '400001',
        })
        response = client.post('/api/auth/login', json={
            'email': 'pending@test.com', 'password': 'Test@1234',
        })
        assert response.status_code == 403


class TestProducts:
    def test_list_products(self, client):
        response = client.get('/api/products')
        assert response.status_code == 200
        assert 'items' in response.json

    def test_get_categories(self, client):
        response = client.get('/api/categories')
        assert response.status_code == 200


class TestAuthorization:
    def test_admin_dashboard_requires_auth(self, client):
        response = client.get('/api/admin/dashboard')
        assert response.status_code == 401

    def test_cart_requires_auth(self, client):
        response = client.get('/api/cart')
        assert response.status_code == 401
