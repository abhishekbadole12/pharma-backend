from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from marshmallow import ValidationError
from app.extensions import db
from app.middleware.auth import admin_required, client_required
from app.schemas.validation import AddressSchema, ReviewSchema
from app.utils.helpers import serialize_doc, paginate, utc_now

addresses_bp = Blueprint('addresses', __name__)
wishlist_bp = Blueprint('wishlist', __name__)
reviews_bp = Blueprint('reviews', __name__)
notifications_bp = Blueprint('notifications', __name__)


# Addresses
@addresses_bp.route('', methods=['GET'])
@client_required
def list_addresses():
    addresses = list(db.addresses.find({'user_id': ObjectId(g.user_id)}).sort('created_at', -1))
    return jsonify({'addresses': serialize_doc(addresses)})


@addresses_bp.route('', methods=['POST'])
@client_required
def create_address():
    try:
        data = AddressSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    address = {
        **data,
        'user_id': ObjectId(g.user_id),
        'is_default': request.get_json().get('is_default', False),
        'created_at': utc_now(),
    }
    if address['is_default']:
        db.addresses.update_many(
            {'user_id': ObjectId(g.user_id)},
            {'$set': {'is_default': False}}
        )
    result = db.addresses.insert_one(address)
    address['_id'] = result.inserted_id
    return jsonify(serialize_doc(address)), 201


@addresses_bp.route('/<address_id>', methods=['PUT'])
@client_required
def update_address(address_id):
    address = db.addresses.find_one({'_id': ObjectId(address_id), 'user_id': ObjectId(g.user_id)})
    if not address:
        return jsonify({'error': 'Address not found'}), 404
    data = request.get_json()
    allowed = ['full_name', 'phone', 'address', 'apartment', 'city', 'state', 'pincode', 'is_default']
    update = {k: v for k, v in data.items() if k in allowed}
    if update.get('is_default'):
        db.addresses.update_many({'user_id': ObjectId(g.user_id)}, {'$set': {'is_default': False}})
    db.addresses.update_one({'_id': ObjectId(address_id)}, {'$set': update})
    return jsonify(serialize_doc(db.addresses.find_one({'_id': ObjectId(address_id)})))


@addresses_bp.route('/<address_id>', methods=['DELETE'])
@client_required
def delete_address(address_id):
    db.addresses.delete_one({'_id': ObjectId(address_id), 'user_id': ObjectId(g.user_id)})
    return jsonify({'message': 'Address deleted'})


# Wishlist
@wishlist_bp.route('', methods=['GET'])
@client_required
def get_wishlist():
    wishlist = db.wishlists.find_one({'user_id': ObjectId(g.user_id)})
    if not wishlist:
        return jsonify({'items': []})

    items = []
    for pid in wishlist.get('product_ids', []):
        product = db.products.find_one({'_id': ObjectId(pid) if isinstance(pid, str) else pid, 'status': 'ACTIVE'})
        if product:
            items.append(serialize_doc(product))
    return jsonify({'items': items})


@wishlist_bp.route('/<product_id>', methods=['POST'])
@client_required
def add_to_wishlist(product_id):
    db.wishlists.update_one(
        {'user_id': ObjectId(g.user_id)},
        {'$addToSet': {'product_ids': product_id}, '$setOnInsert': {'created_at': utc_now()}},
        upsert=True
    )
    return jsonify({'message': 'Added to wishlist'})


@wishlist_bp.route('/<product_id>', methods=['DELETE'])
@client_required
def remove_from_wishlist(product_id):
    db.wishlists.update_one(
        {'user_id': ObjectId(g.user_id)},
        {'$pull': {'product_ids': product_id}}
    )
    return jsonify({'message': 'Removed from wishlist'})


@wishlist_bp.route('/<product_id>/move-to-cart', methods=['POST'])
@client_required
def move_to_cart(product_id):
    from app.routes.cart import get_or_create_cart
    product = db.products.find_one({'_id': ObjectId(product_id), 'status': 'ACTIVE'})
    if not product:
        return jsonify({'error': 'Product not available'}), 404

    cart = get_or_create_cart(g.user_id)
    items = cart.get('items', [])
    found = False
    for item in items:
        if item['product_id'] == product_id:
            found = True
            break
    if not found:
        items.append({'product_id': product_id, 'quantity': 1})
        db.carts.update_one({'user_id': ObjectId(g.user_id)}, {'$set': {'items': items, 'updated_at': utc_now()}})

    db.wishlists.update_one({'user_id': ObjectId(g.user_id)}, {'$pull': {'product_ids': product_id}})
    return jsonify({'message': 'Moved to cart'})


# Reviews
@reviews_bp.route('', methods=['GET'])
def list_reviews():
    product_id = request.args.get('product_id')
    page = request.args.get('page', 1)
    query = {'visible': True}
    if product_id:
        query['product_id'] = ObjectId(product_id)
    result = paginate(db.reviews, query, page=page, per_page=10, sort=[('created_at', -1)])

    items = []
    for review in result['items']:
        review_data = serialize_doc(review)
        user = db.users.find_one({'_id': review['user_id']})
        if user:
            review_data['user_name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        items.append(review_data)

    return jsonify({'items': items, 'total': result['total'], 'page': result['page'], 'pages': result['pages']})


@reviews_bp.route('', methods=['POST'])
@client_required
def create_review():
    try:
        data = ReviewSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    existing = db.reviews.find_one({
        'product_id': ObjectId(data['product_id']),
        'user_id': ObjectId(g.user_id)
    })
    if existing:
        return jsonify({'error': 'You have already reviewed this product'}), 409

    delivered_order = db.orders.find_one({
        'user_id': ObjectId(g.user_id),
        'status': 'DELIVERED',
        'items.product_id': data['product_id']
    })
    if not delivered_order:
        return jsonify({'error': 'You can only review products you have purchased and received'}), 403

    review = {
        'product_id': ObjectId(data['product_id']),
        'user_id': ObjectId(g.user_id),
        'rating': data['rating'],
        'review_text': data['review_text'],
        'verified_purchase': True,
        'visible': True,
        'created_at': utc_now(),
    }
    result = db.reviews.insert_one(review)
    review['_id'] = result.inserted_id
    return jsonify(serialize_doc(review)), 201


@reviews_bp.route('/admin', methods=['GET'])
@admin_required
def admin_list_reviews():
    page = request.args.get('page', 1)
    result = paginate(db.reviews, {}, page=page, per_page=20, sort=[('created_at', -1)])
    items = []
    for review in result['items']:
        review_data = serialize_doc(review)
        user = db.users.find_one({'_id': review['user_id']})
        product = db.products.find_one({'_id': review['product_id']})
        review_data['user_name'] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() if user else 'Unknown'
        review_data['product_name'] = product.get('name') if product else 'Unknown'
        items.append(review_data)
    return jsonify({'items': items, 'total': result['total'], 'page': result['page'], 'pages': result['pages']})


@reviews_bp.route('/<review_id>/visibility', methods=['PUT'])
@admin_required
def toggle_review_visibility(review_id):
    review = db.reviews.find_one({'_id': ObjectId(review_id)})
    if not review:
        return jsonify({'error': 'Review not found'}), 404
    new_visible = not review.get('visible', True)
    db.reviews.update_one({'_id': ObjectId(review_id)}, {'$set': {'visible': new_visible}})
    return jsonify({'message': 'Review visibility updated', 'visible': new_visible})


@reviews_bp.route('/<review_id>', methods=['DELETE'])
@admin_required
def delete_review(review_id):
    db.reviews.delete_one({'_id': ObjectId(review_id)})
    return jsonify({'message': 'Review deleted'})


# Notifications
@notifications_bp.route('', methods=['GET'])
@client_required
def get_notifications():
    from app.services.notification_service import NotificationService
    page = request.args.get('page', 1)
    result = NotificationService.get_user_notifications(g.user_id, page)
    return jsonify({
        'items': serialize_doc(result['items']),
        'total': result['total'],
        'unread_count': NotificationService.unread_count(g.user_id),
    })


@notifications_bp.route('/<notification_id>/read', methods=['PUT'])
@client_required
def mark_notification_read(notification_id):
    from app.services.notification_service import NotificationService
    NotificationService.mark_read(notification_id, g.user_id)
    return jsonify({'message': 'Notification marked as read'})


@notifications_bp.route('/read-all', methods=['PUT'])
@client_required
def mark_all_read():
    from app.services.notification_service import NotificationService
    NotificationService.mark_all_read(g.user_id)
    return jsonify({'message': 'All notifications marked as read'})
