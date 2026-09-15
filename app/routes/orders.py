from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from marshmallow import ValidationError
from app.extensions import db
from app.middleware.auth import client_required, admin_required
from app.schemas.validation import OrderCreateSchema
from app.services.order_service import OrderService
from app.utils.helpers import serialize_doc, paginate, utc_now
from app.utils.storage import get_storage, allowed_file, ALLOWED_PRESCRIPTION_EXTENSIONS

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('', methods=['POST'])
@client_required
def create_order():
    try:
        data = OrderCreateSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    address = db.addresses.find_one({
        '_id': ObjectId(data['address_id']),
        'user_id': ObjectId(g.user_id)
    })
    if not address:
        return jsonify({'error': 'Address not found'}), 404

    order, error = OrderService.create_order(
        g.user_id,
        serialize_doc(address),
        data.get('prescription_id') or None
    )
    if error:
        return jsonify({'error': error}), 400

    return jsonify({'message': 'Order placed successfully', 'order': serialize_doc(order)}), 201


@orders_bp.route('', methods=['GET'])
@client_required
def list_orders():
    page = request.args.get('page', 1)
    status = request.args.get('status')
    query = {'user_id': ObjectId(g.user_id)}
    if status:
        query['status'] = status
    result = paginate(db.orders, query, page=page, per_page=10, sort=[('created_at', -1)])
    return jsonify({
        'items': serialize_doc(result['items']),
        'total': result['total'],
        'page': result['page'],
        'pages': result['pages'],
    })


@orders_bp.route('/<order_id>', methods=['GET'])
@client_required
def get_order(order_id):
    order = db.orders.find_one({
        '_id': ObjectId(order_id),
        'user_id': ObjectId(g.user_id)
    })
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    history = list(db.order_history.find({'order_id': order['_id']}).sort('created_at', 1))
    order_data = serialize_doc(order)
    order_data['history'] = serialize_doc(history)
    return jsonify(order_data)


@orders_bp.route('/<order_id>/cancel', methods=['POST'])
@client_required
def cancel_order(order_id):
    success, result = OrderService.cancel_order(order_id, g.user_id)
    if not success:
        return jsonify({'error': result}), 400
    return jsonify({'message': 'Order cancelled', 'order': serialize_doc(result)})


@orders_bp.route('/admin', methods=['GET'])
@admin_required
def admin_list_orders():
    page = request.args.get('page', 1)
    status = request.args.get('status')
    search = request.args.get('search', '')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = {}
    if status:
        query['status'] = status
    if search:
        query['$or'] = [
            {'order_number': {'$regex': search, '$options': 'i'}},
        ]
    if date_from or date_to:
        query['created_at'] = {}
        if date_from:
            from datetime import datetime
            query['created_at']['$gte'] = datetime.fromisoformat(date_from)
        if date_to:
            from datetime import datetime
            query['created_at']['$lte'] = datetime.fromisoformat(date_to)

    result = paginate(db.orders, query, page=page, per_page=20, sort=[('created_at', -1)])
    items = []
    for order in result['items']:
        order_data = serialize_doc(order)
        user = db.users.find_one({'_id': order['user_id']})
        if user:
            order_data['customer'] = {
                'name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                'email': user.get('email'),
                'phone': user.get('phone'),
            }
        items.append(order_data)

    return jsonify({
        'items': items,
        'total': result['total'],
        'page': result['page'],
        'pages': result['pages'],
    })


@orders_bp.route('/admin/<order_id>', methods=['GET'])
@admin_required
def admin_get_order(order_id):
    order = db.orders.find_one({'_id': ObjectId(order_id)})
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    user = db.users.find_one({'_id': order['user_id']})
    history = list(db.order_history.find({'order_id': order['_id']}).sort('created_at', 1))
    prescription = None
    if order.get('prescription_id'):
        prescription = db.prescriptions.find_one({'_id': order['prescription_id']})

    order_data = serialize_doc(order)
    order_data['customer'] = serialize_doc(user) if user else None
    order_data['history'] = serialize_doc(history)
    order_data['prescription'] = serialize_doc(prescription)
    return jsonify(order_data)


@orders_bp.route('/prescription', methods=['POST'])
@client_required
def upload_prescription():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not allowed_file(file.filename, ALLOWED_PRESCRIPTION_EXTENSIONS):
        return jsonify({'error': 'Invalid file type. Allowed: png, jpg, jpeg, pdf'}), 400

    storage = get_storage()
    url = storage.save(file, 'prescriptions')

    prescription = {
        'user_id': ObjectId(g.user_id),
        'file_url': url,
        'status': 'PENDING',
        'created_at': utc_now(),
    }
    result = db.prescriptions.insert_one(prescription)

    from app.services.notification_service import NotificationService
    NotificationService.notify_admins(
        'Prescription Upload',
        'A new prescription has been uploaded for review',
        'info', '/admin/orders'
    )

    return jsonify({
        'message': 'Prescription uploaded',
        'prescription_id': str(result.inserted_id),
        'file_url': url
    }), 201


@orders_bp.route('/admin/prescriptions', methods=['GET'])
@admin_required
def admin_list_prescriptions():
    page = request.args.get('page', 1)
    status = request.args.get('status')
    query = {}
    if status:
        query['status'] = status
    result = paginate(db.prescriptions, query, page=page, per_page=20, sort=[('created_at', -1)])
    items = []
    for p in result['items']:
        doc = serialize_doc(p)
        user = db.users.find_one({'_id': p['user_id']})
        doc['user'] = serialize_doc(user) if user else None
        items.append(doc)
    return jsonify({'items': items, 'total': result['total'], 'page': result['page'], 'pages': result['pages']})


@orders_bp.route('/admin/prescriptions/<prescription_id>/status', methods=['PUT'])
@admin_required
def admin_update_prescription_status(prescription_id):
    data = request.get_json() or {}
    new_status = data.get('status')
    note = data.get('note', '')
    if new_status not in ['APPROVED', 'REJECTED', 'PENDING']:
        return jsonify({'error': 'Invalid status'}), 400

    pres = db.prescriptions.find_one({'_id': ObjectId(prescription_id)})
    if not pres:
        return jsonify({'error': 'Prescription not found'}), 404

    db.prescriptions.update_one({'_id': pres['_id']}, {'$set': {'status': new_status, 'review_note': note, 'reviewed_at': utc_now()}})

    # if linked to orders, update prescription_status on those orders
    db.orders.update_many({'prescription_id': pres['_id']}, {'$set': {'prescription_status': new_status}})

    # notify user
    user = db.users.find_one({'_id': pres['user_id']})
    if user:
        from app.services.notification_service import NotificationService
        NotificationService.create(str(pres['user_id']), 'Prescription Update', f'Your prescription status: {new_status}', 'info', '/orders')

    return jsonify({'message': 'Prescription status updated'})
