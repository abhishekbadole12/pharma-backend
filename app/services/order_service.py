import uuid
from bson import ObjectId
from app.extensions import db
from app.utils.helpers import utc_now
from app.services.inventory_service import InventoryService
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService


class OrderService:
    ORDER_STATUSES = [
        'PLACED', 'CONFIRMED', 'PROCESSING', 'SHIPPED',
        'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED'
    ]

    CANCELLABLE_STATUSES = ['PLACED', 'CONFIRMED']

    @staticmethod
    def calculate_order(user_id, cart_items):
        items = []
        prescription_required = False

        for cart_item in cart_items:
            product = db.products.find_one({'_id': ObjectId(cart_item['product_id'])})
            if not product or product.get('status') != 'ACTIVE':
                continue
            qty = cart_item.get('quantity', 1)
            if product.get('prescription_required'):
                prescription_required = True
            items.append({
                'product_id': str(product['_id']),
                'name': product.get('name'),
                'slug': product.get('slug'),
                'sku': product.get('sku'),
                'quantity': qty,
                'thumbnail': product.get('thumbnail', ''),
                'prescription_required': product.get('prescription_required', False),
            })

        return {
            'items': items,
            'prescription_required': prescription_required,
        }

    @staticmethod
    def create_order(user_id, address, prescription_id=None):
        user = db.users.find_one({'_id': ObjectId(user_id)})
        cart = db.carts.find_one({'user_id': ObjectId(user_id)})
        if not cart or not cart.get('items'):
            return None, 'Cart is empty'

        calculation = OrderService.calculate_order(user_id, cart['items'])

        if calculation['prescription_required'] and not prescription_id:
            return None, 'Prescription required for some items in cart'

        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order = {
            'order_number': order_number,
            'user_id': ObjectId(user_id),
            'items': calculation['items'],
            'status': 'PLACED',
            'shipping_address': address,
            'prescription_id': ObjectId(prescription_id) if prescription_id else None,
            'prescription_status': 'PENDING' if prescription_id else None,
            'created_at': utc_now(),
            'updated_at': utc_now(),
        }

        result = db.orders.insert_one(order)
        order_id = result.inserted_id
        order['_id'] = order_id

        OrderService.add_history(str(order_id), 'PLACED', 'Order placed', user_id)

        db.carts.update_one(
            {'user_id': ObjectId(user_id)},
            {'$set': {'items': [], 'updated_at': utc_now()}}
        )

        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        EmailService.send_order_confirmation(user['email'], name, order)
        NotificationService.create(user_id, 'Order Placed', f'Your order #{order_number} has been placed', 'success', f'/orders/{str(order_id)}')
        NotificationService.notify_admins('New Order', f'New order #{order_number} received', 'info', f'/admin/orders/{str(order_id)}')

        return order, None

    @staticmethod
    def add_history(order_id, status, note='', changed_by=None):
        entry = {
            'order_id': ObjectId(order_id),
            'status': status,
            'note': note,
            'changed_by': ObjectId(changed_by) if changed_by else None,
            'created_at': utc_now(),
        }
        db.order_history.insert_one(entry)

    @staticmethod
    def update_status(order_id, new_status, note='', admin_id=None):
        if new_status not in OrderService.ORDER_STATUSES:
            return False, 'Invalid status'

        order = db.orders.find_one({'_id': ObjectId(order_id)})
        if not order:
            return False, 'Order not found'

        old_status = order.get('status')
        if old_status == new_status:
            return True, order

        if new_status == 'CANCELLED' and old_status not in OrderService.CANCELLABLE_STATUSES:
            return False, 'Order cannot be cancelled at this stage'

        update = {'status': new_status, 'updated_at': utc_now()}
        if new_status == 'DELIVERED':
            update['delivered_at'] = utc_now()
        if new_status == 'CANCELLED':
            update['cancelled_at'] = utc_now()

        db.orders.update_one({'_id': ObjectId(order_id)}, {'$set': update})
        OrderService.add_history(order_id, new_status, note, admin_id)

        user = db.users.find_one({'_id': order['user_id']})
        if user:
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            EmailService.send_order_status_update(user['email'], name, order, new_status)
            NotificationService.create(
                str(order['user_id']),
                'Order Update',
                f'Order #{order["order_number"]} status: {new_status.replace("_", " ").title()}',
                'info',
                f'/orders/{order_id}'
            )

        order['status'] = new_status
        return True, order

    @staticmethod
    def cancel_order(order_id, user_id):
        order = db.orders.find_one({'_id': ObjectId(order_id), 'user_id': ObjectId(user_id)})
        if not order:
            return False, 'Order not found'
        if order['status'] not in OrderService.CANCELLABLE_STATUSES:
            return False, 'Order cannot be cancelled'
        return OrderService.update_status(order_id, 'CANCELLED', 'Cancelled by customer', user_id)
