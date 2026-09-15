from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from marshmallow import ValidationError
from app.extensions import db
from app.middleware.auth import client_required
from app.schemas.validation import CartItemSchema
from app.services.order_service import OrderService
from app.utils.helpers import serialize_doc, utc_now

cart_bp = Blueprint('cart', __name__)


def get_or_create_cart(user_id):
    cart = db.carts.find_one({'user_id': ObjectId(user_id)})
    if not cart:
        cart = {
            'user_id': ObjectId(user_id),
            'items': [],
            'created_at': utc_now(),
            'updated_at': utc_now(),
        }
        result = db.carts.insert_one(cart)
        cart['_id'] = result.inserted_id
    return cart


@cart_bp.route('', methods=['GET'])
@client_required
def get_cart():
    cart = get_or_create_cart(g.user_id)
    items_with_details = []
    for item in cart.get('items', []):
        product = db.products.find_one({'_id': ObjectId(item['product_id'])})
        if product and product.get('status') == 'ACTIVE':
            items_with_details.append({
                'product_id': str(product['_id']),
                'name': product.get('name'),
                'slug': product.get('slug'),
                'quantity': item['quantity'],
                'thumbnail': product.get('thumbnail', ''),
                'prescription_required': product.get('prescription_required', False),
            })

    return jsonify({
        'items': items_with_details,
        'prescription_required': any(item.get('prescription_required') for item in items_with_details),
    })


@cart_bp.route('/items', methods=['POST'])
@client_required
def add_item():
    try:
        data = CartItemSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    product = db.products.find_one({'_id': ObjectId(data['product_id']), 'status': 'ACTIVE'})
    if not product:
        return jsonify({'error': 'Product not available'}), 404

    cart = get_or_create_cart(g.user_id)
    items = cart.get('items', [])
    found = False
    for item in items:
        if item['product_id'] == data['product_id']:
            new_qty = item['quantity'] + data['quantity']
            item['quantity'] = new_qty
            found = True
            break
    if not found:
        items.append({'product_id': data['product_id'], 'quantity': data['quantity']})

    db.carts.update_one(
        {'user_id': ObjectId(g.user_id)},
        {'$set': {'items': items, 'updated_at': utc_now()}}
    )
    return jsonify({'message': 'Item added to cart'})


@cart_bp.route('/items/<product_id>', methods=['PUT'])
@client_required
def update_item(product_id):
    quantity = request.get_json().get('quantity', 1)
    if quantity < 1:
        return jsonify({'error': 'Quantity must be at least 1'}), 400

    product = db.products.find_one({'_id': ObjectId(product_id), 'status': 'ACTIVE'})
    if not product:
        return jsonify({'error': 'Product not available'}), 404
    cart = get_or_create_cart(g.user_id)
    items = cart.get('items', [])
    updated = False
    for item in items:
        if item['product_id'] == product_id:
            item['quantity'] = quantity
            updated = True
            break
    if not updated:
        return jsonify({'error': 'Item not in cart'}), 404

    db.carts.update_one(
        {'user_id': ObjectId(g.user_id)},
        {'$set': {'items': items, 'updated_at': utc_now()}}
    )
    return jsonify({'message': 'Cart updated'})


@cart_bp.route('/items/<product_id>', methods=['DELETE'])
@client_required
def remove_item(product_id):
    db.carts.update_one(
        {'user_id': ObjectId(g.user_id)},
        {'$pull': {'items': {'product_id': product_id}}, '$set': {'updated_at': utc_now()}}
    )
    return jsonify({'message': 'Item removed from cart'})


@cart_bp.route('', methods=['DELETE'])
@client_required
def clear_cart():
    db.carts.update_one(
        {'user_id': ObjectId(g.user_id)},
        {'$set': {'items': [], 'updated_at': utc_now()}}
    )
    return jsonify({'message': 'Cart cleared'})
