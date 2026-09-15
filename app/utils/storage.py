import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
import io

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:
    boto3 = None


ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_PRESCRIPTION_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}


def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


class LocalStorage:
    def __init__(self, upload_dir=None):
        self.upload_dir = upload_dir or current_app.config['UPLOAD_DIR']

    def save(self, file, subfolder=''):
        if not file or not file.filename:
            return None
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        folder = os.path.join(self.upload_dir, subfolder)
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return f"/uploads/{subfolder}/{filename}" if subfolder else f"/uploads/{filename}"

    def delete(self, filepath):
        if not filepath:
            return
        full_path = os.path.join(self.upload_dir, filepath.replace('/uploads/', ''))
        if os.path.exists(full_path):
            os.remove(full_path)


def get_storage():
    provider = current_app.config.get('STORAGE_PROVIDER', 'local')
    if provider == 's3' and boto3:
        return S3Storage(
            bucket=current_app.config.get('S3_BUCKET'),
            region=current_app.config.get('AWS_REGION'),
            access_key=current_app.config.get('AWS_ACCESS_KEY_ID'),
            secret_key=current_app.config.get('AWS_SECRET_ACCESS_KEY'),
        )
    return LocalStorage()


class S3Storage:
    def __init__(self, bucket, region='us-east-1', access_key=None, secret_key=None):
        self.bucket = bucket
        self.region = region
        session_kwargs = {}
        if access_key and secret_key:
            session_kwargs = {
                'aws_access_key_id': access_key,
                'aws_secret_access_key': secret_key,
                'region_name': region,
            }
        self.s3 = boto3.session.Session(**session_kwargs).client('s3')

    def _key_for(self, subfolder, filename):
        key = f"{subfolder}/{filename}" if subfolder else filename
        return key

    def save(self, file, subfolder=''):
        if not file or not file.filename:
            return None
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        key = self._key_for(subfolder, filename)
        try:
            # read file content
            file.stream.seek(0)
            data = file.read()
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        except (BotoCoreError, ClientError) as e:
            current_app.logger.exception('S3 upload failed')
            return None
        # construct public URL (assumes bucket public or CDN)
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def delete(self, filepath):
        if not filepath:
            return
        # attempt to extract key from URL
        if filepath.startswith('http'):
            key = '/'.join(filepath.split('/')[3:])
        else:
            key = filepath.replace('/uploads/', '')
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            current_app.logger.exception('S3 delete failed')
