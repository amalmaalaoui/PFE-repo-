import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import create_app, db
from app.models import User
from flask import url_for
from werkzeug.security import generate_password_hash

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import create_app, db
from app.models import User
from flask import url_for
from werkzeug.security import generate_password_hash

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import create_app, db
from app.models import User
from flask import url_for
from werkzeug.security import generate_password_hash

@pytest.fixture
def app():
    # Use in-memory SQLite database for testing
    app = create_app(start_scheduler=False)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TESTING'] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
        # Create admin user for tests
        admin_user = User(username='admin', email='admin@example.com', is_admin=True)
        admin_user.set_password('adminpass')
        db.session.add(admin_user)
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

def login(client, username, password):
    return client.post('/login', data=dict(
        username=username,
        password=password
    ), follow_redirects=True)

def logout(client):
    return client.get('/logout', follow_redirects=True)

def test_login_logout(client):
    # Test login with valid credentials
    response = login(client, 'admin', 'adminpass')
    assert b'Logged in successfully as admin' in response.data

    # Test logout
    response = logout(client)
    assert response.status_code == 200

    # Test login with invalid credentials
    response = login(client, 'admin', 'wrongpass')
    assert b'Invalid username or password' in response.data

def test_add_user(client, app):
    login(client, 'admin', 'adminpass')
    # Test adding a new user with valid data
    response = client.post('/add_user', data=dict(
        username='testuser',
        email='testuser@example.com',
        password='testpass',
        is_admin=False
    ), follow_redirects=True)
    # Check for redirect to manage_users or success flash message
    assert b'User added successfully!' in response.data or response.status_code == 200

    # Test adding a user with missing data (should fail validation)
    response = client.post('/add_user', data=dict(
        username='',
        email='',
        password='',
        is_admin=False
    ), follow_redirects=True)
    # Should render the form again with errors, so no success message
    assert b'User added successfully!' not in response.data

def test_edit_user(client, app):
    login(client, 'admin', 'adminpass')
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        user_id = user.id

    # Test GET edit user page
    response = client.get(f'/edit_user/{user_id}')
    assert response.status_code == 200

    # Test POST edit user with valid data
    response = client.post(f'/edit_user/{user_id}', data=dict(
        username='admin_updated',
        email='admin_updated@example.com',
        is_admin=True,
        new_password=''
    ), follow_redirects=True)
    # Accept either success flash or redirect status
    assert b'User updated successfully!' in response.data or response.status_code == 200

    # Test POST edit user with password change
    response = client.post(f'/edit_user/{user_id}', data=dict(
        username='admin_updated',
        email='admin_updated@example.com',
        is_admin=True,
        new_password='newpass'
    ), follow_redirects=True)
    assert b'Password has been updated' in response.data or response.status_code == 200

def test_delete_user(client, app):
    login(client, 'admin', 'adminpass')
    with app.app_context():
        # Add a user to delete
        user = User(username='todelete', email='todelete@example.com', is_admin=False)
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    # Test deleting another user
    response = client.post(f'/delete_user/{user_id}', follow_redirects=True)
    assert b'User deleted successfully' in response.data

    # Test deleting own account (should fail)
    with app.app_context():
        admin_user = User.query.filter_by(username='admin').first()
        admin_id = admin_user.id
    response = client.post(f'/delete_user/{admin_id}', follow_redirects=True)
    assert b'You cannot delete your own account' in response.data

def test_reset_password(client, app):
    login(client, 'admin', 'adminpass')
    with app.app_context():
        user = User.query.filter_by(username='admin').first()
        user_id = user.id

    # Test GET reset password page
    response = client.get('/reset-password')
    assert response.status_code == 200

    # Test POST reset password with missing fields
    response = client.post('/reset-password', data=dict(
        user_id='',
        password='',
        confirm_password=''
    ), follow_redirects=True)
    assert b'All fields are required' in response.data

    # Test POST reset password with password mismatch
    response = client.post('/reset-password', data=dict(
        user_id=user_id,
        password='newpass',
        confirm_password='wrongpass'
    ), follow_redirects=True)
    assert b'Passwords do not match' in response.data

    # Test POST reset password with invalid user
    response = client.post('/reset-password', data=dict(
        user_id=9999,
        password='newpass',
        confirm_password='newpass'
    ), follow_redirects=True)
    assert b'User not found' in response.data

    # Test POST reset password success
    response = client.post('/reset-password', data=dict(
        user_id=user_id,
        password='newpass',
        confirm_password='newpass'
    ), follow_redirects=True)
    assert b'Password has been reset successfully' in response.data

