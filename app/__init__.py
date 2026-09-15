import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from app.config import config
from app.extensions import init_extensions, limiter
from app.utils.helpers import setup_logging


SWAGGER_URL = '/api/docs'
API_URL = '/api/swagger.json'

OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Pharma E-Commerce API",
        "description": "REST API for pharmaceutical e-commerce platform",
        "version": "1.0.0"
    },
    "servers": [{"url": "/api"}],
    "paths": {
        "/auth/signup": {"post": {"summary": "Client registration", "tags": ["Auth"]}},
        "/auth/login": {"post": {"summary": "Login", "tags": ["Auth"]}},
        "/auth/logout": {"post": {"summary": "Logout", "tags": ["Auth"]}},
        "/auth/me": {"get": {"summary": "Get current user", "tags": ["Auth"]}},
        "/products": {"get": {"summary": "List products", "tags": ["Products"]}, "post": {"summary": "Create product (Admin)", "tags": ["Products"]}},
        "/products/{id}": {"get": {"summary": "Get product", "tags": ["Products"]}},
        "/categories": {"get": {"summary": "List categories", "tags": ["Categories"]}},
        "/cart": {"get": {"summary": "Get cart", "tags": ["Cart"]}},
        "/orders": {"get": {"summary": "List orders", "tags": ["Orders"]}, "post": {"summary": "Create order", "tags": ["Orders"]}},
        "/admin/dashboard": {"get": {"summary": "Admin dashboard stats", "tags": ["Admin"]}},
        "/admin/approvals": {"get": {"summary": "Pending approvals", "tags": ["Admin"]}},
    },
    "components": {
        "securitySchemes": {
            "cookieAuth": {"type": "apiKey", "in": "cookie", "name": "access_token"}
        }
    }
}


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    CORS(app, origins=[app.config['FRONTEND_URL'], 'http://localhost:3000'],
         supports_credentials=True)

    setup_logging(app)
    init_extensions(app)

    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.products import products_bp
    from app.routes.categories import categories_bp
    from app.routes.cart import cart_bp
    from app.routes.orders import orders_bp
    from app.routes.misc import addresses_bp, wishlist_bp, reviews_bp, notifications_bp
    from app.routes.inventory import inventory_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(products_bp, url_prefix='/api/products')
    app.register_blueprint(categories_bp, url_prefix='/api/categories')
    app.register_blueprint(cart_bp, url_prefix='/api/cart')
    app.register_blueprint(orders_bp, url_prefix='/api/orders')
    app.register_blueprint(inventory_bp, url_prefix='/api/inventory')
    app.register_blueprint(addresses_bp, url_prefix='/api/addresses')
    app.register_blueprint(wishlist_bp, url_prefix='/api/wishlist')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

    swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={'app_name': "Pharma E-Commerce API"})
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    @app.route('/api/swagger.json')
    def swagger_spec():
        return jsonify(OPENAPI_SPEC)

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'healthy', 'service': 'pharma-ecommerce-api'})

    @app.route('/uploads/<path:filename>')
    def serve_uploads(filename):
        upload_dir = app.config['UPLOAD_DIR']
        return send_from_directory(upload_dir, filename)

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"Server error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(429)
    def rate_limit(e):
        return jsonify({'error': 'Too many requests. Please try again later.'}), 429

    return app
