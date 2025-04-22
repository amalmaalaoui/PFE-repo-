from app import create_app, db
from app.models import User

def reset_admin_password(new_password='admin'):
    app = create_app()
    with app.app_context():
        admin_user = User.query.filter_by(is_admin=True).first()
        if not admin_user:
            print("Admin user not found.")
            return
        admin_user.set_password(new_password)
        db.session.commit()
        print(f"Admin password has been reset to: {new_password}")

if __name__ == '__main__':
    reset_admin_password()
