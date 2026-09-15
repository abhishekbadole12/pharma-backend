"""Seed database with initial data."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from slugify import slugify
from app import create_app
import app.extensions as extensions
from app.services.auth_service import AuthService
from app.utils.helpers import utc_now


def build_product_media(index):
    media = [
        'https://images.unsplash.com/photo-1584515933487-779824d29309?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1607619056574-7b8d0f4dbb66?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1576091160550-2173dba999ef?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1550572017-6d0d7d3dffe1?auto=format&fit=crop&w=900&q=80',
        'https://images.unsplash.com/photo-1523398002811-999ca3a4b9d2?auto=format&fit=crop&w=900&q=80',
    ]
    selected = media[index % len(media)]
    return [selected, media[(index + 1) % len(media)]]


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

        medicines = [
            ('Paracetamol 500mg', 'MED-PARA-500', 'Crocin', 25, 30, 500, False, 'Paracetamol 500mg', 'GSK Pharmaceuticals'),
            ('Ibuprofen 400mg', 'MED-IBU-400', 'Brufen', 35, 45, 400, False, 'Ibuprofen 400mg', 'Abbott'),
            ('Cetirizine 10mg', 'MED-CET-10', 'Zyrtec', 20, 28, 600, False, 'Cetirizine Hydrochloride 10mg', 'UCB Pharma'),
            ('Omeprazole 20mg', 'MED-OME-20', 'Omez', 45, 60, 300, True, 'Omeprazole 20mg', "Dr. Reddy's"),
            ('Metformin 500mg', 'MED-MET-500', 'Glycomet', 55, 70, 350, True, 'Metformin Hydrochloride 500mg', 'USV Limited'),
            ('Azithromycin 500mg', 'MED-AZI-500', 'Azithral', 120, 150, 200, True, 'Azithromycin 500mg', 'Alembic Pharmaceuticals'),
            ('Amlodipine 5mg', 'MED-AMLO-5', 'Amlip', 30, 40, 250, True, 'Amlodipine 5mg', 'Cipla'),
            ('ORS Lemon Sachets', 'MED-ORS-01', 'Electral', 25, 30, 450, False, 'Oral Rehydration Salts', 'FDC Limited'),
            ('Antacid Suspension  mint', 'MED-ANTI-170', 'Digene', 110, 135, 180, False, 'Antacid Suspension 170ml', 'Abbott'),
            ('Povidone Iodine Solution', 'MED-POV-100', 'Betadine', 95, 120, 160, False, 'Povidone Iodine 10%', 'Win-Medicare'),
        ]

        medicines_category = category_ids['Medicines']
        for index, (name, sku, brand, price, mrp, stock, prescription, composition, manufacturer) in enumerate(medicines):
            if db.products.find_one({'sku': sku}):
                continue
            images = build_product_media(index)
            db.products.insert_one({
                'name': name,
                'slug': slugify(name),
                'sku': sku,
                'category_id': medicines_category,
                'subcategory': '',
                'brand': brand,
                'description': f'Quality {name} from {brand}.',
                'short_description': f'{name} - {brand}',
                'price': price,
                'mrp': mrp,
                'discount': round((1 - price / mrp) * 100, 1),
                'stock_quantity': stock,
                'low_stock_threshold': 20,
                'images': images,
                'thumbnail': images[0],
                'tags': ['medicines', brand.lower()],
                'product_type': 'PRESCRIPTION' if prescription else 'OTC',
                'prescription_required': prescription,
                'status': 'ACTIVE',
                'featured': index < 3,
                'best_seller': index < 2,
                'composition': composition,
                'manufacturer': manufacturer,
                'dosage': 'As directed by physician',
                'usage': 'Take as prescribed',
                'warnings': 'Keep out of reach of children',
                'storage': 'Store in a cool, dry place',
                'expiry_info': 'Check packaging for expiry date',
                'created_at': utc_now(),
                'updated_at': utc_now(),
            })

        print('  Default medicines are configured')

        print("Seeding complete!")


if __name__ == '__main__':
    seed()