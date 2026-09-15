from flask import Blueprint, request, jsonify
from bson import ObjectId
from app.middleware.auth import admin_required
from app.extensions import db
from app.services.inventory_service import InventoryService
from app.utils.helpers import serialize_doc, paginate

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/adjust', methods=['POST'])
@admin_required
def adjust_stock():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    change = int(data.get('change', 0))
    reason = data.get('reason', 'adjustment')
    if not product_id:
        return jsonify({'error': 'product_id required'}), 400
    success, result = InventoryService.adjust_stock(product_id, change, reason=reason)
    if not success:
        return jsonify({'error': result}), 400
    return jsonify({'message': 'Stock adjusted', 'new_stock': result})


@inventory_bp.route('/history/<product_id>', methods=['GET'])
@admin_required
def stock_history(product_id):
    page = request.args.get('page', 1)
    query = {'product_id': ObjectId(product_id)}
    result = paginate(db.stock_history, query, page=page, per_page=20, sort=[('created_at', -1)])
    return jsonify({'items': serialize_doc(result['items']), 'total': result['total'], 'page': result['page'], 'pages': result['pages']})


@inventory_bp.route('/low-stock', methods=['GET'])
@admin_required
def low_stock():
    threshold = int(request.args.get('threshold', 10))
    items = list(db.products.find({'stock_quantity': {'$lte': threshold}}).sort('stock_quantity', 1))
    return jsonify({'items': serialize_doc(items)})
