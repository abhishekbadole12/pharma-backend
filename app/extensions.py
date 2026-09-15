from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

db = None
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])


def init_extensions(app):
    global db
    client = MongoClient(app.config['MONGO_URI'])
    db = client[app.config['MONGO_DB_NAME']]
    limiter.init_app(app)

    # Create indexes
    _create_indexes(db)


def _create_indexes(database):
    database.users.create_index('email', unique=True)
    database.users.create_index('phone')
    database.products.create_index('slug', unique=True)
    database.products.create_index('sku', unique=True)
    database.products.create_index([('name', 'text'), ('brand', 'text'), ('tags', 'text')])
    database.categories.create_index('slug', unique=True)
    database.orders.create_index('order_number', unique=True)
    database.orders.create_index('user_id')
    database.offers.create_index('offer_code', unique=True)
    database.carts.create_index('user_id', unique=True)
    database.wishlists.create_index('user_id', unique=True)
    database.notifications.create_index('user_id')
    database.reviews.create_index([('product_id', 1), ('user_id', 1)])
