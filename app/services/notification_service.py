from bson import ObjectId
from app.extensions import db
from app.utils.helpers import utc_now


class NotificationService:
    @staticmethod
    def create(user_id, title, message, ntype='info', link=''):
        notification = {
            'user_id': ObjectId(user_id) if isinstance(user_id, str) else user_id,
            'title': title,
            'message': message,
            'type': ntype,
            'link': link,
            'read': False,
            'created_at': utc_now(),
        }
        result = db.notifications.insert_one(notification)
        notification['_id'] = result.inserted_id
        return notification

    @staticmethod
    def notify_admins(title, message, ntype='info', link=''):
        admins = db.users.find({'role': 'ADMIN'})
        for admin in admins:
            NotificationService.create(str(admin['_id']), title, message, ntype, link)

    @staticmethod
    def get_user_notifications(user_id, page=1, per_page=20):
        from app.utils.helpers import paginate
        return paginate(
            db.notifications,
            {'user_id': ObjectId(user_id)},
            page=page,
            per_page=per_page,
            sort=[('created_at', -1)]
        )

    @staticmethod
    def mark_read(notification_id, user_id):
        db.notifications.update_one(
            {'_id': ObjectId(notification_id), 'user_id': ObjectId(user_id)},
            {'$set': {'read': True}}
        )

    @staticmethod
    def mark_all_read(user_id):
        db.notifications.update_many(
            {'user_id': ObjectId(user_id), 'read': False},
            {'$set': {'read': True}}
        )

    @staticmethod
    def unread_count(user_id):
        return db.notifications.count_documents({
            'user_id': ObjectId(user_id),
            'read': False
        })
