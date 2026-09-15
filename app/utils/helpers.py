import logging
import sys
from datetime import datetime, timezone
from bson import ObjectId


def setup_logging(app):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def utc_now():
    return datetime.now(timezone.utc)


def serialize_doc(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if key == '_id':
                result['id'] = str(value)
            elif key == 'password_hash':
                continue
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = serialize_doc(value)
            elif isinstance(value, list):
                result[key] = serialize_doc(value)
            else:
                result[key] = value
        return result
    return doc


def paginate(collection, query, page=1, per_page=20, sort=None):
    page = max(1, int(page))
    per_page = min(100, max(1, int(per_page)))
    skip = (page - 1) * per_page
    total = collection.count_documents(query)
    cursor = collection.find(query)
    if sort:
        cursor = cursor.sort(sort)
    items = list(cursor.skip(skip).limit(per_page))
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page if total > 0 else 0,
    }
