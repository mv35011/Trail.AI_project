from app import create_app
from app.auth import auth, login_manager
app = create_app()
login_manager.init_app(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')