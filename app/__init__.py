from enum import Enum
from json import JSONEncoder
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from pytz import timezone
from os import getenv
from dotenv import load_dotenv
# Initialize extensions without app
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.unauthorized_handler = 'main.login'
migrate = Migrate()
scheduler = APScheduler()  # This is all you need

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)
    
def create_app(start_scheduler=False):
    app = Flask(__name__)
    app.json_encoder = CustomJSONEncoder
    tunis_tz = timezone('Africa/Tunis')
    # Configuration
    app.config['SECRET_KEY'] = 'your-secret-key-here'
    # Fix SSL configuration in SQLALCHEMY_DATABASE_URI
    load_dotenv()  # Load environment variables from a .env file
    app.config['SQLALCHEMY_DATABASE_URI'] = getenv('DBURI', '')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'app/static/uploads'
    app.config['MIGRATION_FOLDER'] = 'app/static/migrations'
    app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}
    app.config['SCHEDULER_JOBSTORES'] = {
        'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
    }
    app.config['SCHEDULER_JOB_DEFAULTS'] = {
        'coalesce': False,
        'max_instances': 3,
        'misfire_grace_time': 3600  # 1 hour
    }
    
    # Scheduler configuration (corrected - no space)
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = tunis_tz.zone
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize scheduler with app    
    if start_scheduler:
        scheduler.init_app(app)
        scheduler.start()
    
    # Register blueprints
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Import models after db initialization
    from app import models
    
    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables and default admin
    with app.app_context():
        db.create_all()
        
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