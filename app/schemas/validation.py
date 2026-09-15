from marshmallow import Schema, fields, validate, validates, ValidationError
import re


class SignupSchema(Schema):
    class Meta:
        unknown = 'exclude'

    email = fields.Email(required=True)
    phone = fields.Str(required=True, validate=validate.Length(min=10, max=15))
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))

    @validates('password')
    def validate_password(self, value):
        if not re.search(r'[A-Z]', value):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', value):
            raise ValidationError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', value):
            raise ValidationError('Password must contain at least one digit')

    @validates('confirm_password')
    def validate_confirm(self, value, **kwargs):
        pass


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)
    remember_me = fields.Bool(load_default=False)


class ProductSchema(Schema):
    name = fields.Str(required=True)
    sku = fields.Str(required=True)
    category_id = fields.Str(required=True)
    subcategory = fields.Str(load_default='')
    brand = fields.Str(required=True)
    description = fields.Str(load_default='')
    short_description = fields.Str(load_default='')
    stock_quantity = fields.Int(load_default=0, validate=validate.Range(min=0))
    low_stock_threshold = fields.Int(load_default=10)
    tags = fields.List(fields.Str(), load_default=[])
    product_type = fields.Str(load_default='OTC')
    prescription_required = fields.Bool(load_default=False)
    status = fields.Str(validate=validate.OneOf(['ACTIVE', 'INACTIVE', 'OUT_OF_STOCK']), load_default='ACTIVE')
    featured = fields.Bool(load_default=False)
    best_seller = fields.Bool(load_default=False)
    composition = fields.Str(load_default='')
    manufacturer = fields.Str(load_default='')
    dosage = fields.Str(load_default='')
    usage = fields.Str(load_default='')
    warnings = fields.Str(load_default='')
    storage = fields.Str(load_default='')
    expiry_info = fields.Str(load_default='')


class CategorySchema(Schema):
    name = fields.Str(required=True)
    description = fields.Str(load_default='')
    parent_id = fields.Str(load_default=None)
    status = fields.Str(validate=validate.OneOf(['ACTIVE', 'INACTIVE']), load_default='ACTIVE')


class AddressSchema(Schema):
    full_name = fields.Str(required=True)
    phone = fields.Str(required=True)
    address = fields.Str(required=True)
    apartment = fields.Str(load_default='')
    city = fields.Str(required=True)
    state = fields.Str(required=True)
    pincode = fields.Str(required=True)
    is_default = fields.Bool(load_default=False)


class ReviewSchema(Schema):
    product_id = fields.Str(required=True)
    rating = fields.Int(required=True, validate=validate.Range(min=1, max=5))
    review_text = fields.Str(required=True, validate=validate.Length(min=10, max=1000))


class CartItemSchema(Schema):
    product_id = fields.Str(required=True)
    quantity = fields.Int(required=True, validate=validate.Range(min=1))


class OrderCreateSchema(Schema):
    address_id = fields.Str(required=True)
    prescription_id = fields.Str(load_default='')
