from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint
from enum import Enum
from sqlalchemy.dialects.postgresql import JSON
import json
import hashlib
import hmac
import os

class FileType(Enum):
    SOURCE = 'source'
    TARGET = 'target'
    MIGRATION = 'migration'

class MigrationStatus(str, Enum):
    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SCHEDULED = 'SCHEDULED'

    def __str__(self):
        return self.value
    
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint('length(username) >= 3', name='username_min_length'),
        CheckConstraint('length(email) >= 5', name='email_min_length')
    )
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    migrations = db.relationship('Migration', backref='user', lazy=True)
    files = db.relationship('UserFile', backref='user', lazy=True)

    def set_password(self, password):
        salt = os.urandom(16)
        hashed_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        self.password_hash = f"{salt.hex()}:{hashed_password.hex()}"

    def check_password(self, password):
        try:
            salt, hashed_password = self.password_hash.split(':')
            salt = bytes.fromhex(salt)
            expected_hash = bytes.fromhex(hashed_password)
            provided_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return hmac.compare_digest(provided_hash, expected_hash)
        except ValueError:
            return False

class UserFile(db.Model):
    __tablename__ = 'user_files'
    __table_args__ = (
        CheckConstraint('size > 0', name='file_size_positive'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    size = db.Column(db.Integer, nullable=False)
    sheet_count = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.Enum(FileType), nullable=False, default=FileType.SOURCE)
    sheet_names = db.Column(db.Text, nullable=True)

    def set_sheet_names(self, names_list):
        self.sheet_names = json.dumps(names_list)

    def get_sheet_names(self):
        try:
            return json.loads(self.sheet_names) if self.sheet_names else []
        except json.JSONDecodeError:
            return []

class Migration(db.Model):
    __tablename__ = 'migrations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    source_file = db.Column(db.String(500), nullable=False)
    target_file = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    block_count = db.Column(db.Integer)
    scheduled_time = db.Column(db.DateTime)
    job_id = db.Column(db.String(100))
    status = db.Column(db.String(50), default=MigrationStatus.PENDING.value, nullable=False)
    log_file_path = db.Column(db.String(500))
    result_file_path = db.Column(db.String(500))
    
    @property
    def status_enum(self):
        return MigrationStatus(self.status)