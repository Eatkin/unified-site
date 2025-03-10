from google.cloud import storage
from firebase_admin import firestore, initialize_app

# Firestore
initialize_app()
DB = firestore.client()

# Google Cloud Storage
STORAGE_CLIENT = storage.Client()
BUCKET = STORAGE_CLIENT.bucket('website-content54321')

# Constants
ITEMS_PER_PAGE = 10
CONTENT_TYPES = {
    'blog': 'blogs',
    'project': 'projects',
    'comic': 'comics',
    'music': 'music',
    'video': 'videos',
    'game': 'games'
}
ROUTER = {
    'project': 'project.html',
    'blog': 'blog.html',
    'comic': 'comic.html',
    'music': 'music.html',
    'video': 'video.html',
    'game': 'game.html'
}
