from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from slugify import slugify
from app.extensions import db
from app.middleware.auth import admin_required, client_required, login_required
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.utils.helpers import serialize_doc, paginate, utc_now

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    total_orders = db.orders.count_documents({})
    pending_orders = db.orders.count_documents({'status': 'PLACED'})
    processing_orders = db.orders.count_documents({'status': {'$in': ['CONFIRMED', 'PROCESSING']}})
    delivered_orders = db.orders.count_documents({'status': 'DELIVERED'})
    cancelled_orders = db.orders.count_documents({'status': 'CANCELLED'})

    total_customers = db.users.count_documents({'role': 'CLIENT'})
    normal_customers = db.users.count_documents({'role': 'CLIENT', 'client_type': 'NORMAL'})
    retailers = db.users.count_documents({'role': 'CLIENT', 'client_type': 'RETAILER'})
    total_products = db.products.count_documents({})
    low_stock = db.products.count_documents({
        '$expr': {'$lte': ['$stock_quantity', '$low_stock_threshold']},
        'status': 'ACTIVE'
    })

    # Sales by day (last 30 days)
    from datetime import timedelta
    thirty_days_ago = utc_now() - timedelta(days=30)
    sales_by_day = list(db.orders.aggregate([
        {'$match': {'created_at': {'$gte': thirty_days_ago}, 'status': {'$ne': 'CANCELLED'}}},
        {'$group': {
            '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
            'count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}}
    ]))

    # Orders by status
    orders_by_status = list(db.orders.aggregate([
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
    ]))

    # Top selling products
    top_products = list(db.orders.aggregate([
        {'$match': {'status': {'$ne': 'CANCELLED'}}},
        {'$unwind': '$items'},
        {'$group': {
            '_id': '$items.product_id',
            'name': {'$first': '$items.name'},
            'total_sold': {'$sum': '$items.quantity'},
        }},
        {'$sort': {'total_sold': -1}},
        {'$limit': 10}
    ]))

    # Customer distribution
    customer_distribution = [
        {'type': 'Normal', 'count': normal_customers},
        {'type': 'Retailer', 'count': retailers},
    ]

    # Sales by month (last 12 months)
    twelve_months_ago = utc_now() - timedelta(days=365)
    sales_by_month = list(db.orders.aggregate([
        {'$match': {'created_at': {'$gte': twelve_months_ago}, 'status': {'$ne': 'CANCELLED'}}},
        {'$group': {
            '_id': {'$dateToString': {'format': '%Y-%m', 'date': '$created_at'}},
            'count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}}
    ]))

    return jsonify({
        'stats': {
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'processing_orders': processing_orders,
            'delivered_orders': delivered_orders,
            'cancelled_orders': cancelled_orders,
            'total_customers': total_customers,
            'normal_customers': normal_customers,
            'retailers': retailers,
            'total_products': total_products,
            'low_stock_products': low_stock,
        },
        'charts': {
            'sales_by_day': sales_by_day,
            'sales_by_month': sales_by_month,
            'orders_by_status': orders_by_status,
            'customer_distribution': customer_distribution,
            'top_products': top_products,
        }
    })


@admin_bp.route('/approvals', methods=['GET'])
@admin_required
def get_approvals():
    status = request.args.get('status', 'PENDING')
    page = request.args.get('page', 1)
    query = {'role': 'CLIENT'}
    if status:
        query['status'] = status
    result = paginate(db.users, query, page=page, per_page=20, sort=[('created_at', -1)])
    return jsonify({
        'items': serialize_doc(result['items']),
        'total': result['total'],
        'page': result['page'],
        'pages': result['pages'],
    })


@admin_bp.route('/approvals/<user_id>/approve', methods=['POST'])
@admin_required
def approve_client(user_id):
    user = db.users.find_one({'_id': ObjectId(user_id), 'role': 'CLIENT'})
    if not user:
        return jsonify({'error': 'Client not found'}), 404

    db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'status': 'APPROVED', 'updated_at': utc_now()}}
    )

    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    EmailService.send_client_approved(user['email'], name)
    NotificationService.create(
        user_id, 'Account Approved',
        'Your account has been approved. You can now shop!',
        'success', '/shop'
    )

    return jsonify({'message': 'Client approved successfully'})


@admin_bp.route('/approvals/<user_id>/reject', methods=['POST'])
@admin_required
def reject_client(user_id):
    user = db.users.find_one({'_id': ObjectId(user_id), 'role': 'CLIENT'})
    if not user:
        return jsonify({'error': 'Client not found'}), 404

    reason = request.get_json().get('reason', '')
    db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'status': 'REJECTED', 'rejection_reason': reason, 'updated_at': utc_now()}}
    )

    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    EmailService.send_client_rejected(user['email'], name, reason)

    return jsonify({'message': 'Client rejected'})


@admin_bp.route('/customers', methods=['GET'])
@admin_required
def get_customers():
    page = request.args.get('page', 1)
    client_type = request.args.get('client_type')
    status = request.args.get('status')
    search = request.args.get('search', '')

    query = {'role': 'CLIENT'}
    if client_type:
        query['client_type'] = client_type
    if status:
        query['status'] = status
    if search:
        query['$or'] = [
            {'email': {'$regex': search, '$options': 'i'}},
            {'first_name': {'$regex': search, '$options': 'i'}},
            {'last_name': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
        ]

    result = paginate(db.users, query, page=page, per_page=20, sort=[('created_at', -1)])
    customers = []
    for user in result['items']:
        user_data = serialize_doc(user)
        order_stats = list(db.orders.aggregate([
            {'$match': {'user_id': user['_id'], 'status': {'$ne': 'CANCELLED'}}},
            {'$group': {'_id': None, 'count': {'$sum': 1}}}
        ]))
        user_data['total_orders'] = order_stats[0]['count'] if order_stats else 0
        customers.append(user_data)

    return jsonify({
        'items': customers,
        'total': result['total'],
        'page': result['page'],
        'pages': result['pages'],
    })


@admin_bp.route('/customers/<user_id>/suspend', methods=['POST'])
@admin_required
def suspend_customer(user_id):
    db.users.update_one(
        {'_id': ObjectId(user_id), 'role': 'CLIENT'},
        {'$set': {'status': 'SUSPENDED', 'updated_at': utc_now()}}
    )
    return jsonify({'message': 'Customer suspended'})


@admin_bp.route('/customers/<user_id>/reactivate', methods=['POST'])
@admin_required
def reactivate_customer(user_id):
    db.users.update_one(
        {'_id': ObjectId(user_id), 'role': 'CLIENT'},
        {'$set': {'status': 'APPROVED', 'updated_at': utc_now()}}
    )
    return jsonify({'message': 'Customer reactivated'})


@admin_bp.route('/orders/<order_id>/status', methods=['PUT'])
@admin_required
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get('status')
    note = data.get('note', '')

    from app.services.order_service import OrderService
    success, result = OrderService.update_status(order_id, new_status, note, g.user_id)
    if not success:
        return jsonify({'error': result}), 400
    return jsonify({'message': 'Order status updated', 'order': serialize_doc(result)})


@admin_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    settings = db.settings.find_one({'type': 'store'}) or {}
    return jsonify(serialize_doc(settings))


@admin_bp.route('/settings', methods=['PUT'])
@admin_required
def update_settings():
    data = request.get_json()
    allowed = [
        'store_name', 'store_email', 'store_phone', 'address',
        'currency', 'shipping_charges', 'free_shipping_threshold',
        'tax_percentage', 'order_prefix'
    ]
    update = {k: v for k, v in data.items() if k in allowed}
    update['updated_at'] = utc_now()
    db.settings.update_one(
        {'type': 'store'},
        {'$set': update, '$setOnInsert': {'type': 'store'}},
        upsert=True
    )
    return jsonify({'message': 'Settings updated'})
