from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from slugify import slugify
from marshmallow import ValidationError
from app.extensions import db
from app.middleware.auth import admin_required, client_required
from app.schemas.validation import ProductSchema
from app.utils.helpers import serialize_doc, paginate, utc_now
from app.utils.storage import get_storage, allowed_file, ALLOWED_IMAGE_EXTENSIONS

products_bp = Blueprint('products', __name__)


def serialize_product(product):
    if product is None:
        return None
    serialized = serialize_doc(product)
    for field in ('price', 'mrp', 'discount'):
        serialized.pop(field, None)
    return serialized


def serialize_products(products):
    return [serialize_product(product) for product in products]


@products_bp.route('', methods=['GET'])
def list_products():
    page = request.args.get('page', 1)
    per_page = request.args.get('per_page', 20)
    search = request.args.get('search', '')
    category = request.args.get('category')
    brand = request.args.get('brand')
    prescription = request.args.get('prescription_required')
    featured = request.args.get('featured')
    best_seller = request.args.get('best_seller')
    sort = request.args.get('sort', 'newest')
    status = request.args.get('status', 'ACTIVE')

    query = {}
    if status:
        query['status'] = status
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'brand': {'$regex': search, '$options': 'i'}},
            {'sku': {'$regex': search, '$options': 'i'}},
            {'tags': {'$regex': search, '$options': 'i'}},
        ]
    if category:
        query['category_id'] = ObjectId(category)
    if brand:
        query['brand'] = {'$regex': brand, '$options': 'i'}
    if prescription == 'true':
        query['prescription_required'] = True
    elif prescription == 'false':
        query['prescription_required'] = False
    if featured == 'true':
        query['featured'] = True
    if best_seller == 'true':
        query['best_seller'] = True

    sort_map = {
        'newest': [('created_at', -1)],
        'name': [('name', 1)],
    }
    sort_field = sort_map.get(sort, [('created_at', -1)])

    result = paginate(db.products, query, page=page, per_page=per_page, sort=sort_field)
    return jsonify({
        'items': serialize_products(result['items']),
        'total': result['total'],
        'page': result['page'],
        'pages': result['pages'],
        'per_page': result['per_page'],
    })


@products_bp.route('/search', methods=['GET'])
def search_products():
    q = request.args.get('q', '')
    limit = min(int(request.args.get('limit', 10)), 20)
    if not q or len(q) < 2:
        return jsonify({'suggestions': []})

    products = db.products.find(
        {'$text': {'$search': q}, 'status': 'ACTIVE'},
        {'score': {'$meta': 'textScore'}}
    ).sort([('score', {'$meta': 'textScore'})]).limit(limit)

    suggestions = []
    for p in products:
        suggestions.append({
            'id': str(p['_id']),
            'name': p.get('name'),
            'slug': p.get('slug'),
            'thumbnail': p.get('thumbnail', ''),
            'brand': p.get('brand', ''),
        })
    return jsonify({'suggestions': suggestions})


@products_bp.route('/<product_id>', methods=['GET'])
def get_product(product_id):
    try:
        product = db.products.find_one({'_id': ObjectId(product_id)})
    except Exception:
        product = db.products.find_one({'slug': product_id})

    if not product:
        return jsonify({'error': 'Product not found'}), 404

    category = db.categories.find_one({'_id': product.get('category_id')})
    related = list(db.products.find({
        'category_id': product.get('category_id'),
        '_id': {'$ne': product['_id']},
        'status': 'ACTIVE'
    }).limit(8))

    reviews = list(db.reviews.find({
        'product_id': product['_id'],
        'visible': True
    }).sort('created_at', -1).limit(10))

    avg_rating = list(db.reviews.aggregate([
        {'$match': {'product_id': product['_id'], 'visible': True}},
        {'$group': {'_id': None, 'avg': {'$avg': '$rating'}, 'count': {'$sum': 1}}}
    ]))

    product_data = serialize_product(product)
    product_data['category'] = serialize_doc(category)
    product_data['related_products'] = serialize_products(related)
    product_data['reviews'] = serialize_doc(reviews)
    if avg_rating:
        product_data['average_rating'] = round(avg_rating[0]['avg'], 1)
        product_data['review_count'] = avg_rating[0]['count']
    else:
        product_data['average_rating'] = 0
        product_data['review_count'] = 0

    return jsonify(product_data)


@products_bp.route('', methods=['POST'])
@admin_required
def create_product():
    try:
        data = ProductSchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    slug = slugify(data['name'])
    if db.products.find_one({'slug': slug}):
        slug = f"{slug}-{ObjectId()}"
    if db.products.find_one({'sku': data['sku']}):
        return jsonify({'error': 'SKU already exists'}), 409

    product = {
        **data,
        'slug': slug,
        'category_id': ObjectId(data['category_id']),
        'images': [],
        'thumbnail': '',
        'created_at': utc_now(),
        'updated_at': utc_now(),
    }
    result = db.products.insert_one(product)
    product['_id'] = result.inserted_id
    return jsonify(serialize_doc(product)), 201


@products_bp.route('/<product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    product = db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    data = request.get_json()
    allowed = [
        'name', 'sku', 'subcategory', 'brand', 'description', 'short_description',
        'stock_quantity', 'low_stock_threshold', 'tags',
        'product_type', 'prescription_required', 'status', 'featured', 'best_seller',
        'composition', 'manufacturer', 'dosage', 'usage', 'warnings', 'storage', 'expiry_info'
    ]
    update = {k: v for k, v in data.items() if k in allowed}
    if 'category_id' in data:
        update['category_id'] = ObjectId(data['category_id'])
    if 'name' in update:
        update['slug'] = slugify(update['name'])
    update['updated_at'] = utc_now()

    db.products.update_one({'_id': ObjectId(product_id)}, {'$set': update})
    updated = db.products.find_one({'_id': ObjectId(product_id)})
    return jsonify(serialize_doc(updated))


@products_bp.route('/<product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    result = db.products.delete_one({'_id': ObjectId(product_id)})
    if result.deleted_count == 0:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify({'message': 'Product deleted'})


@products_bp.route('/<product_id>/upload', methods=['POST'])
@admin_required
def upload_product_image(product_id):
    product = db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
        return jsonify({'error': 'Invalid file type'}), 400

    storage = get_storage()
    url = storage.save(file, 'products')
    is_thumbnail = request.form.get('is_thumbnail') == 'true'

    update = {'$push': {'images': url}, '$set': {'updated_at': utc_now()}}
    if is_thumbnail or not product.get('thumbnail'):
        update['$set']['thumbnail'] = url

    db.products.update_one({'_id': ObjectId(product_id)}, update)
    return jsonify({'url': url, 'message': 'Image uploaded'})


@products_bp.route('/<product_id>/images', methods=['DELETE'])
@admin_required
def delete_product_image(product_id):
    product = db.products.find_one({'_id': ObjectId(product_id)})
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({'error': 'url required'}), 400

    db.products.update_one({'_id': ObjectId(product_id)}, {'$pull': {'images': url}, '$set': {'updated_at': utc_now()}})

    # if thumbnail was this image, clear or set next image as thumbnail
    if product.get('thumbnail') == url:
        remaining = [u for u in product.get('images', []) if u != url]
        new_thumb = remaining[0] if remaining else ''
        db.products.update_one({'_id': ObjectId(product_id)}, {'$set': {'thumbnail': new_thumb, 'updated_at': utc_now()}})

    # attempt to delete from storage
    try:
        storage = get_storage()
        storage.delete(url)
    except Exception:
        pass

    return jsonify({'message': 'Image removed'})


@products_bp.route('/brands', methods=['GET'])
def get_brands():
    brands = db.products.distinct('brand', {'status': 'ACTIVE'})
    return jsonify({'brands': sorted(brands)})
