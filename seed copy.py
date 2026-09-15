"""Seed database with initial data."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from slugify import slugify
from app import create_app
import app.extensions as extensions
from app.services.auth_service import AuthService
from app.utils.helpers import utc_now


def build_product_media(name, brand, index=0):
    """Return seeded product artwork for frontend product cards."""
    media = [
        'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1607619056574-7b8d0f4dbb66?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1550572017-6d0d7d3dffe1?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1523398002811-999ca3a4b9d2?auto=format&fit=crop&w=900&q=80',
    ]
    selected = media[index % len(media)]
    return {
        'thumbnail': selected,
        'images': [selected, media[(index + 1) % len(media)]],
    }


def seed():
    app = create_app()
    with app.app_context():
        print("Seeding database...")

        # Admin user
        admin_email = app.config['ADMIN_EMAIL']
        db = extensions.db
        if not db.users.find_one({'email': admin_email}):
            AuthService.create_user({
                'email': admin_email,
                'password': app.config['ADMIN_PASSWORD'],
                'first_name': 'Admin',
                'last_name': 'User',
                'phone': '9999999999',
            }, role='ADMIN')
            print(f"  Created admin: {admin_email}")

        # Sample clients
        clients = [
            {
                'email': 'john.doe@example.com', 'password': 'Client@123',
                'first_name': 'John', 'last_name': 'Doe', 'phone': '9876543210',
                'client_type': 'NORMAL', 'status': 'APPROVED',
                'address': {'street': '123 Main St', 'city': 'Mumbai', 'state': 'Maharashtra', 'pincode': '400001'},
            },
            {
                'email': 'retailer@example.com', 'password': 'Client@123',
                'first_name': 'Pharma', 'last_name': 'Store', 'phone': '9876543211',
                'client_type': 'RETAILER', 'status': 'APPROVED',
                'address': {'street': '456 Market Rd', 'city': 'Delhi', 'state': 'Delhi', 'pincode': '110001'},
                'business': {'name': 'Pharma Store Pvt Ltd', 'gst_number': '27AABCU9603R1ZM', 'address': '456 Market Rd, Delhi'},
            },
        ]
        for c in clients:
            if not db.users.find_one({'email': c['email']}):
                user = AuthService.create_user(c)
                db.users.update_one({'_id': user['_id']}, {'$set': {'status': c['status']}})
                print(f"  Created client: {c['email']}")

        # Store settings
        db.settings.update_one(
            {'type': 'store'},
            {'$set': {
                'type': 'store',
                'store_name': 'PharmaCare',
                'store_email': 'support@pharmacare.com',
                'store_phone': '1800-123-4567',
                'address': 'Shitlapara Opposite. Shitla Mata Mandir, kanker',
                'currency': 'INR',
                'shipping_charges': 50,
                'free_shipping_threshold': 500,
                'tax_percentage': 18,
            }},
            upsert=True
        )
        print("  Store settings configured")

        # Categories
        categories_data = [
            'Medicines', 'Vitamins & Supplements', 'Personal Care',
            'Healthcare Devices', 'Pain Relief', 'Diabetes Care',
            'Skin Care', 'Baby Care', 'Wellness'
        ]
        category_ids = {}
        for name in categories_data:
            slug = slugify(name)
            existing = db.categories.find_one({'slug': slug})
            if existing:
                category_ids[name] = existing['_id']
            else:
                result = db.categories.insert_one({
                    'name': name, 'slug': slug, 'description': f'{name} products',
                    'image': '', 'status': 'ACTIVE', 'parent_id': None,
                    'created_at': utc_now(), 'updated_at': utc_now(),
                })
                category_ids[name] = result.inserted_id
        print(f"  Created {len(categories_data)} categories")

        # Products
        products_data = [
            {'name': 'Paracetamol 500mg', 'sku': 'MED-PARA-500', 'brand': 'Crocin', 'category': 'Medicines',
             'price': 25, 'mrp': 30, 'stock': 500, 'prescription': False, 'featured': True, 'best_seller': True,
             'composition': 'Paracetamol 500mg', 'manufacturer': 'GSK Pharmaceuticals'},
            {'name': 'Vitamin D3 60000 IU', 'sku': 'VIT-D3-60K', 'brand': 'HealthVit', 'category': 'Vitamins & Supplements',
             'price': 180, 'mrp': 250, 'stock': 200, 'prescription': False, 'featured': True,
             'composition': 'Cholecalciferol 60000 IU', 'manufacturer': 'HealthVit Labs'},
            {'name': 'Omeprazole 20mg', 'sku': 'MED-OME-20', 'brand': 'Omez', 'category': 'Medicines',
             'price': 45, 'mrp': 60, 'stock': 300, 'prescription': True, 'featured': False,
             'composition': 'Omeprazole 20mg', 'manufacturer': 'Dr. Reddy\'s'},
            {'name': 'Digital Thermometer', 'sku': 'DEV-THERM-01', 'brand': 'Dr. Morepen', 'category': 'Healthcare Devices',
             'price': 299, 'mrp': 450, 'stock': 100, 'prescription': False, 'featured': True,
             'manufacturer': 'Dr. Morepen Limited'},
            {'name': 'Blood Glucose Monitor', 'sku': 'DEV-BG-01', 'brand': 'Accu-Chek', 'category': 'Diabetes Care',
             'price': 1299, 'mrp': 1599, 'stock': 50, 'prescription': False, 'featured': True, 'best_seller': True,
             'manufacturer': 'Roche Diabetes Care'},
            {'name': 'Ibuprofen 400mg', 'sku': 'MED-IBU-400', 'brand': 'Brufen', 'category': 'Pain Relief',
             'price': 35, 'mrp': 45, 'stock': 400, 'prescription': False, 'best_seller': True,
             'composition': 'Ibuprofen 400mg', 'manufacturer': 'Abbott'},
            {'name': 'Cetirizine 10mg', 'sku': 'MED-CET-10', 'brand': 'Zyrtec', 'category': 'Medicines',
             'price': 20, 'mrp': 28, 'stock': 600, 'prescription': False,
             'composition': 'Cetirizine Hydrochloride 10mg', 'manufacturer': 'UCB Pharma'},
            {'name': 'Moisturizing Lotion 200ml', 'sku': 'SKIN-LOT-200', 'brand': 'Cetaphil', 'category': 'Skin Care',
             'price': 450, 'mrp': 550, 'stock': 150, 'prescription': False, 'featured': True,
             'manufacturer': 'Galderma'},
            {'name': 'Baby Diapers Pack (M)', 'sku': 'BABY-DIA-M', 'brand': 'Pampers', 'category': 'Baby Care',
             'price': 899, 'mrp': 1099, 'stock': 80, 'prescription': False,
             'manufacturer': 'Procter & Gamble'},
            {'name': 'Multivitamin Tablets', 'sku': 'VIT-MULTI-01', 'brand': 'Centrum', 'category': 'Wellness',
             'price': 350, 'mrp': 450, 'stock': 250, 'prescription': False, 'featured': True, 'best_seller': True,
             'composition': 'Multivitamin & Minerals', 'manufacturer': 'Pfizer'},
            {'name': 'Hand Sanitizer 500ml', 'sku': 'PC-SAN-500', 'brand': 'Dettol', 'category': 'Personal Care',
             'price': 199, 'mrp': 250, 'stock': 300, 'prescription': False,
             'manufacturer': 'Reckitt Benckiser'},
            {'name': 'Metformin 500mg', 'sku': 'MED-MET-500', 'brand': 'Glycomet', 'category': 'Diabetes Care',
             'price': 55, 'mrp': 70, 'stock': 350, 'prescription': True,
             'composition': 'Metformin Hydrochloride 500mg', 'manufacturer': 'USV Limited'},
        ]

        for idx, p in enumerate(products_data):
            if db.products.find_one({'sku': p['sku']}):
                continue
            discount = round((1 - p['price'] / p['mrp']) * 100, 1) if p['mrp'] > 0 else 0
            media = build_product_media(p['name'], p['brand'], idx)
            db.products.insert_one({
                'name': p['name'], 'slug': slugify(p['name']), 'sku': p['sku'],
                'category_id': category_ids[p['category']], 'subcategory': '',
                'brand': p['brand'], 'description': f"High quality {p['name']} from {p['brand']}.",
                'short_description': f"{p['name']} - {p['brand']}",
                'price': p['price'], 'mrp': p['mrp'], 'discount': discount,
                'stock_quantity': p['stock'], 'low_stock_threshold': 20,
                'images': media['images'], 'thumbnail': media['thumbnail'],
                'tags': [p['category'].lower(), p['brand'].lower()],
                'product_type': 'OTC' if not p.get('prescription') else 'PRESCRIPTION',
                'prescription_required': p.get('prescription', False),
                'status': 'ACTIVE', 'featured': p.get('featured', False),
                'best_seller': p.get('best_seller', False),
                'composition': p.get('composition', ''), 'manufacturer': p.get('manufacturer', ''),
                'dosage': 'As directed by physician', 'usage': 'Take as prescribed',
                'warnings': 'Keep out of reach of children', 'storage': 'Store in a cool, dry place',
                'expiry_info': 'Check packaging for expiry date',
                'created_at': utc_now(), 'updated_at': utc_now(),
            })
        print(f"  Created {len(products_data)} products")

        # Sample offer
        if not db.offers.find_one({'offer_code': 'WELCOME10'}):
            db.offers.insert_one({
                'offer_name': 'Welcome Discount', 'offer_code': 'WELCOME10',
                'discount_type': 'PERCENTAGE', 'discount_value': 10,
                'minimum_order_amount': 200, 'maximum_discount': 100,
                'start_date': utc_now() - timedelta(days=30),
                'end_date': utc_now() + timedelta(days=365),
                'usage_limit': 1000, 'usage_count': 0,
                'applicable_products': [], 'applicable_categories': [],
                'client_type': 'ALL', 'status': 'ACTIVE',
                'created_at': utc_now(), 'updated_at': utc_now(),
            })
            print("  Created WELCOME10 coupon")

        print("Seeding complete!")


if __name__ == '__main__':
    seed()
