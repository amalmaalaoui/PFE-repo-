from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

# Initialize extensions without app
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'your-secret-key-here'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/qtpmigrator'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'app/static/uploads'
    app.config['MIGRATION_FOLDER'] = 'app/static/migrations'
    app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Import and register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Import models after db initialization
    from app import models
    
    # User loader for Flask-Login
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables and default admin
    with app.app_context():
        db.create_all()
        
        # Check if admin exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@qtpmigrator.com',
                is_admin=True
            )
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
    
    return app
