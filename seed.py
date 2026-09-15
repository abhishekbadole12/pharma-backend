"""Seed database with initial data."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slugify import slugify
from app import create_app
import app.extensions as extensions
from app.services.auth_service import AuthService
from app.utils.helpers import utc_now


def seed():
    app = create_app()

    with app.app_context():
        print("Seeding database...")

        # Database
        db = extensions.db

        # ---------------------------------------------------------
        # Admin user
        # ---------------------------------------------------------
        admin_email = app.config['ADMIN_EMAIL']

        if not db.users.find_one({'email': admin_email}):
            AuthService.create_user({
                'email': admin_email,
                'password': app.config['ADMIN_PASSWORD'],
                'first_name': 'Admin',
                'last_name': 'User',
                'phone': '9999999999',
            }, role='ADMIN')

            print(f"  Created admin: {admin_email}")

        # ---------------------------------------------------------
        # Sample clients
        # ---------------------------------------------------------
        clients = [
            {
                'email': 'john.doe@example.com',
                'password': 'Client@123',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '9876543210',
                'client_type': 'NORMAL',
                'status': 'APPROVED',
                'address': {
                    'street': '123 Main St',
                    'city': 'Mumbai',
                    'state': 'Maharashtra',
                    'pincode': '400001'
                },
            },
            {
                'email': 'retailer@example.com',
                'password': 'Client@123',
                'first_name': 'Pharma',
                'last_name': 'Store',
                'phone': '9876543211',
                'client_type': 'RETAILER',
                'status': 'APPROVED',
                'address': {
                    'street': '456 Market Rd',
                    'city': 'Delhi',
                    'state': 'Delhi',
                    'pincode': '110001'
                },
                'business': {
                    'name': 'Pharma Store Pvt Ltd',
                    'gst_number': '27AABCU9603R1ZM',
                    'address': '456 Market Rd, Delhi'
                },
            },
        ]

        for c in clients:
            if not db.users.find_one({'email': c['email']}):
                user = AuthService.create_user(c)

                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'status': c['status']}}
                )

                print(f"  Created client: {c['email']}")

        # ---------------------------------------------------------
        # Store settings
        # ---------------------------------------------------------
        db.settings.update_one(
            {'type': 'store'},
            {
                '$set': {
                    'type': 'store',
                    'store_name': 'PharmaCare',
                    'store_email': 'support@pharmacare.com',
                    'store_phone': '1800-123-4567',
                    'address': '123 Healthcare Avenue, Mumbai, Maharashtra 400001',
                    'currency': 'INR',
                    'shipping_charges': 50,
                    'free_shipping_threshold': 500,
                    'tax_percentage': 18,
                }
            },
            upsert=True
        )

        print("  Store settings configured")

        # ---------------------------------------------------------
        # Categories
        # ---------------------------------------------------------
        categories_data = [
            'Medicines',
            'Vitamins & Supplements',
            'Personal Care',
            'Healthcare Devices',
            'Pain Relief',
            'Diabetes Care',
            'Skin Care',
            'Baby Care',
            'Wellness'
        ]

        category_ids = {}

        for name in categories_data:
            slug = slugify(name)

            existing = db.categories.find_one({'slug': slug})

            if existing:
                category_ids[name] = existing['_id']
            else:
                result = db.categories.insert_one({
                    'name': name,
                    'slug': slug,
                    'description': f'{name} products',
                    'image': '',
                    'status': 'ACTIVE',
                    'parent_id': None,
                    'created_at': utc_now(),
                    'updated_at': utc_now(),
                })

                category_ids[name] = result.inserted_id

        print(f"  Created {len(categories_data)} categories")

        print("  Products are managed through the admin portal")

        print("Seeding complete!")


if __name__ == '__main__':
    seed()