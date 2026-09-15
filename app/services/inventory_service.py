from bson import ObjectId
from app.extensions import db
from app.utils.helpers import utc_now


class InventoryService:
    @staticmethod
    def adjust_stock(product_id, quantity_change, reason='adjustment', order_id=None, admin_id=None):
        product = db.products.find_one({'_id': ObjectId(product_id)})
        if not product:
            return False, 'Product not found'

        new_stock = product.get('stock_quantity', 0) + quantity_change
        if new_stock < 0:
            return False, 'Insufficient stock'

        db.products.update_one(
            {'_id': ObjectId(product_id)},
            {'$set': {
                'stock_quantity': new_stock,
                'updated_at': utc_now(),
            }}
        )

        history_entry = {
            'product_id': ObjectId(product_id),
            'previous_stock': product.get('stock_quantity', 0),
            'new_stock': new_stock,
            'change': quantity_change,
            'reason': reason,
            'order_id': ObjectId(order_id) if order_id else None,
            'admin_id': ObjectId(admin_id) if admin_id else None,
            'created_at': utc_now(),
        }
        db.stock_history.insert_one(history_entry)

        low_threshold = product.get('low_stock_threshold', 10)
        if new_stock <= low_threshold and new_stock > 0:
            from app.services.notification_service import NotificationService
            NotificationService.notify_admins(
                'Low Stock Alert',
                f'{product.get("name")} is low on stock ({new_stock} remaining)',
                'warning',
                f'/admin/products'
            )

        return True, new_stock

    @staticmethod
    def validate_stock(items):
        errors = []
        for item in items:
            product = db.products.find_one({'_id': ObjectId(item['product_id'])})
            if not product:
                errors.append(f"Product not found: {item.get('product_id')}")
                continue
            if product.get('status') != 'ACTIVE':
                errors.append(f"{product.get('name')} is not available")
                continue
            if product.get('stock_quantity', 0) < item.get('quantity', 0):
                errors.append(f"Insufficient stock for {product.get('name')}. Available: {product.get('stock_quantity', 0)}")
        return errors

    @staticmethod
    def reserve_stock(items, order_id):
        for item in items:
            success, result = InventoryService.adjust_stock(
                item['product_id'],
                -item['quantity'],
                reason='order',
                order_id=order_id
            )
            if not success:
                return False, result
        return True, 'Stock reserved'
