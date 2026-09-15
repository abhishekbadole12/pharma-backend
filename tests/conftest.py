import os
import pytest

from app import create_app


@pytest.fixture(scope='session')
def app():
    os.environ['FLASK_ENV'] = 'development'
    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
