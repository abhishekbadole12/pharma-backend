from flask import Blueprint, request, jsonify
from bson import ObjectId
from slugify import slugify
from marshmallow import ValidationError
from app.extensions import db
from app.middleware.auth import admin_required
from app.schemas.validation import CategorySchema
from app.utils.helpers import serialize_doc, utc_now
from app.utils.storage import get_storage, allowed_file, ALLOWED_IMAGE_EXTENSIONS

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('', methods=['GET'])
def list_categories():
    status = request.args.get('status', 'ACTIVE')
    query = {}
    if status:
        query['status'] = status

    categories = list(db.categories.find(query).sort('name', 1))
    for cat in categories:
        cat['subcategories'] = list(db.categories.find({
            'parent_id': cat['_id'],
            'status': 'ACTIVE'
        }).sort('name', 1))
        cat['product_count'] = db.products.count_documents({
            'category_id': cat['_id'],
            'status': 'ACTIVE'
        })

    return jsonify({'categories': serialize_doc(categories)})


@categories_bp.route('/<category_id>', methods=['GET'])
def get_category(category_id):
    try:
        category = db.categories.find_one({'_id': ObjectId(category_id)})
    except Exception:
        category = db.categories.find_one({'slug': category_id})

    if not category:
        return jsonify({'error': 'Category not found'}), 404

    category['subcategories'] = list(db.categories.find({
        'parent_id': category['_id']
    }))
    return jsonify(serialize_doc(category))


@categories_bp.route('', methods=['POST'])
@admin_required
def create_category():
    try:
        data = CategorySchema().load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400

    slug = slugify(data['name'])
    category = {
        'name': data['name'],
        'slug': slug,
        'description': data.get('description', ''),
        'image': '',
        'status': data.get('status', 'ACTIVE'),
        'parent_id': ObjectId(data['parent_id']) if data.get('parent_id') else None,
        'created_at': utc_now(),
        'updated_at': utc_now(),
    }
    result = db.categories.insert_one(category)
    category['_id'] = result.inserted_id
    return jsonify(serialize_doc(category)), 201


@categories_bp.route('/<category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    category = db.categories.find_one({'_id': ObjectId(category_id)})
    if not category:
        return jsonify({'error': 'Category not found'}), 404

    data = request.get_json()
    update = {}
    for field in ['name', 'description', 'status']:
        if field in data:
            update[field] = data[field]
    if 'name' in data:
        update['slug'] = slugify(data['name'])
    if 'parent_id' in data:
        update['parent_id'] = ObjectId(data['parent_id']) if data['parent_id'] else None
    update['updated_at'] = utc_now()

    db.categories.update_one({'_id': ObjectId(category_id)}, {'$set': update})
    updated = db.categories.find_one({'_id': ObjectId(category_id)})
    return jsonify(serialize_doc(updated))


@categories_bp.route('/<category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    product_count = db.products.count_documents({'category_id': ObjectId(category_id)})
    if product_count > 0:
        return jsonify({'error': f'Cannot delete category with {product_count} products'}), 400
    db.categories.delete_one({'_id': ObjectId(category_id)})
    return jsonify({'message': 'Category deleted'})


@categories_bp.route('/<category_id>/upload', methods=['POST'])
@admin_required
def upload_category_image(category_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
        return jsonify({'error': 'Invalid file type'}), 400

    storage = get_storage()
    url = storage.save(file, 'categories')
    db.categories.update_one(
        {'_id': ObjectId(category_id)},
        {'$set': {'image': url, 'updated_at': utc_now()}}
    )
    return jsonify({'url': url})
