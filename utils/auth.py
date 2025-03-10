import os
from pyrebase import pyrebase
from functools import wraps
from flask import session, redirect, url_for

def init_auth():
    pyrebase_config = {
        'apiKey': os.environ.get('FIREBASE_API_KEY'),
        'authDomain': os.environ.get('FIREBASE_AUTH_DOMAIN'),
        'databaseURL': os.environ.get('FIREBASE_DATABASE_URL'),
        'projectId': os.environ.get('FIREBASE_PROJECT_ID'),
        'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET'),
        'messagingSenderId': os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
        'appId': os.environ.get('FIREBASE_APP_ID'),
    }
    auth_app = pyrebase.initialize_app(pyrebase_config)
    auth = auth_app.auth()
    return auth

AUTH = init_auth()

# Decorator for protected routes
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('index'))
        else:
            # Validate the auth token
            try:
                auth.get_account_info(session['user']['idToken'])
            except Exception as e:
                logging.error(e)
                print(e)
                try:
                    # If it's expired we can refresh it
                    refresh_token = session['user']['refreshToken']
                    res = auth.refresh(refresh_token)
                    # Udpate session
                    session['user']['idToken'] = res['idToken']
                    session['user']['refreshToken'] = res['refreshToken']
                except Exception as e:
                    print(e)
                    logging.error(e)
                    return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper
