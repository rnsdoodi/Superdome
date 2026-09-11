from main import app, db, User
from werkzeug.security import generate_password_hash
import os

with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully.")

    # Create default admin user
    if not User.query.filter_by(username='admin').first():
        admin_password = os.environ.get('ADMIN_PASSWORD', '123')
        hashed_pw = generate_password_hash(admin_password, method='pbkdf2:sha256')
        new_user = User(username='admin', password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        print("✅ Default admin user created.")
    else:
        print("ℹ️ Admin user already exists.")