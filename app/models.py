# app/models.py
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import hashlib
import hmac
import base64

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    migrations = db.relationship('Migration', backref='user', lazy=True)
    files = db.relationship('UserFile', backref='user', lazy=True)

    def set_password(self, password):
        # Custom hash: reversing the password and appending a salt
        salt = "custom_salt"
        custom_hash = password[::-1] + salt
        self.password_hash = base64.b64encode(
            hashlib.sha256(custom_hash.encode('utf-8')).digest()
        ).decode('utf-8')

    def check_password(self, password):
        # Custom hash: reversing the password and appending the same salt
        salt = "custom_salt"
        custom_hash = password[::-1] + salt
        expected_hash = base64.b64encode(
            hashlib.sha256(custom_hash.encode('utf-8')).digest()
        ).decode('utf-8')
        if not self.password_hash:
            raise ValueError("Password hash is not set for this user.")
        return hmac.compare_digest(self.password_hash, expected_hash)

class UserFile(db.Model):
    __tablename__ = 'user_files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    size = db.Column(db.Integer)
    sheet_count = db.Column(db.Integer)
    file_type = db.Column(db.String(50))  # e.g., 'source', 'target', 'migration'
    sheet_names = db.Column(db.Text)  # JSON string of sheet names

class Migration(db.Model):
    __tablename__ = 'migrations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    source_file = db.Column(db.String(255), nullable=False)
    target_file = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    block_count = db.Column(db.Integer, nullable=True)
