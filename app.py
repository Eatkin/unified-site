import os
import logging
from random import choice, choices, shuffle
from io import BytesIO
from datetime import datetime as dt
from functools import wraps

import pytz
from flask import Flask, render_template, send_file, abort, request, redirect, Response, url_for, session
from google.cloud import storage
from firebase_admin import firestore, initialize_app
from feedgen.feed import FeedGenerator
from pyrebase import pyrebase
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from utils.md_parser import markdown_parser
from utils.string_utils import strip_punctuation

# Establish a connection to the Google Cloud Storage and Firestore
storage_client = storage.Client()
bucket = storage_client.bucket('website-content54321')
initialize_app()
db = firestore.client()

# Globals
ITEMS_PER_PAGE = 10
content_types = {
    'blog': 'blogs',
    'project': 'projects',
    'comic': 'comics',
    'music': 'music',
    'video': 'videos',
    'game': 'games'
}
router = {
    'project': 'project.html',
    'blog': 'blog.html',
    'comic': 'comic.html',
    'music': 'music.html',
    'video': 'video.html',
    'game': 'game.html'
}

app = Flask(__name__)

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app
)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error=error), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error=error), 500

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

auth = init_auth()
app.secret_key = os.environ.get('APP_SECRET_KEY')

def register_hit(content_type, content_name):
    # Register a hit in our hitcounter collection
    hit_counter_ref = db.collection('hit_counter').document('hits')
    hit_counter = hit_counter_ref.get().to_dict()
    key = os.path.join(content_type, content_name)
    if key in hit_counter:
        hit_counter[key] += 1
    else:
        hit_counter[key] = 1

    hit_counter_ref.set(hit_counter)


def get_blob(blob_type, name):
    """Get a blob from Google Cloud Storage or abort with a 404 if not found"""
    blob_type = content_types.get(blob_type, blob_type)
    try:
        blob = bucket.blob(os.path.join(blob_type, name))
        if not blob.exists():
            print(f"Blob {name} not found")
            # Render error page
            abort(404)
        return blob
    except Exception as e:
        print(e)
        abort(500, e)

def clean_tags(tags):
    """Clean a tag string"""
    return [strip_punctuation(tag).strip().lower().replace(' ', '-') for tag in tags.split(',')]

# TODO: These next 4 functions have a lot of redundancy - like parse_metadata and get_description
# Get description is VERY similar to parse_markdown - can we refactor this? Yes probably
def parse_markdown(blob):
    """Parse a markdown blob into metadata and content"""
    # Parse the markdown content into metadata and content
    md = blob.download_as_string().decode('utf-8')
    # We can capture the section between --- and --- and use it as metadata
    _, metadata, content = md.split('---', 2)
    metadata = parse_metadata(metadata, blob.name)
    content = markdown_parser.convert(content)

    return metadata, content

def parse_music(content):
    """Parse a music markdown blob into metadata, content and track listing"""
    # Split on --- to get metadata, content and track listing
    md = content.download_as_string().decode('utf-8')
    metadata = md.split('---')[1]
    metadata = parse_metadata(metadata, content.name)
    content = md.split('---')[2]
    content = markdown_parser.convert(content)
    track_listing = md.split('---')[3]
    track_listing = parse_track_listing(track_listing)

    # Now we need to return a dict with metadata, content and track listing
    return {
        'metadata': metadata,
        'content': content,
        'track_listing': track_listing
    }

def parse_track_listing(track_listing):
    """Parse a track listing string into a list of dictionaries with title and file"""
    lines = track_listing.split('\n')

    # Strip any empty lines
    lines = [line for line in lines if line]

    tracks = []
    for i in range(0, len(lines), 2):
        title = lines[i].replace('title:', '').strip()
        file = lines[i+1].replace('file:', '').strip()
        tracks.append(
            {
                'title': title,
                'file': file
            }
        )

    return tracks

def get_collection_navigation(metadata, blob_name):
    """Return next, prev, first and last items in a collection of content"""
    # Get the raw file name from the blob name
    blob_name = blob_name.split('/')[-1]
    # Get the collection from metadata
    collection = metadata['collection']
    # Strip punctuation, lowercase, replace spaces with underscores
    collection = strip_punctuation(collection.lower()).replace(' ', '_')
    # Request the collection from Firestore
    data = db.collection('collections').document(collection).get().to_dict()
    idx = data['content'].index(blob_name)

    # Now remove file extensions from the names
    data['content'] = [blob.split('.')[0] for blob in data['content']]

    if len(data['content']) == 1:
        return None

    return {
        'prev': data['content'][idx-1] if idx > 0 else None,
        'next': data['content'][idx+1] if idx < len(data['content'])-1 else None,
        'first': data['content'][0] if idx > 0 else None,
        'last': data['content'][-1] if idx < len(data['content'])-1 else None
    }

def get_recommendations(blob_name):
    recs = db.collection('recommendations').document('recommendations').get().to_dict()
    feed = db.collection('feed').document('content-log').get().to_dict()
    try:
        recs = recs[blob_name]
        rec_details = []
        for_popping = []
        # Loop over and find metadata
        for k, v in feed.items():
            if v['location'] in recs:
                for_popping.append(k)
                rec_details.append(v)


        # Pop the recommendations from the feed
        for k in for_popping:
            feed.pop(k)

        # Also pick out 3 random pages from the feed
        random_pages = choices(list(feed.keys()), k=3)
        random_pages = [feed[page] for page in random_pages]
        rec_details.extend(random_pages)
        # Format the urls
        for page in rec_details:
            arg = page['url'].split('/')[-1]
            page['url'] = url_for('content', content_type=page['type'], content_name=arg)

        # Randomise the recommendations
        shuffle(rec_details)
        return rec_details
    except Exception as e:
        print(e)
        return None


def get_og_tags(metadata):
    """Get Open Graph tags from metadata"""
    # Get the Open Graph tags from a metadata dictionary
    og_tags = {}
    for tags in ['og_title', 'og_description', 'og_image', 'og_type']:
        if tags in metadata:
            og_tags[tags.replace('og_', 'og:')] = metadata[tags]
    return og_tags if og_tags else None


def parse_metadata(metadata, blob_name):
    """Parse the metadata section of a markdown file and return a dictionary"""
    # Parse the metadata section of the markdown file and return a dictionary
    metadata_dict = {}
    for line in metadata.split('\n'):
        if line:
            split_line = line.split(':')
            key = split_line[0].strip()
            # Remove the quotes
            value = ":".join(split_line[1:]).strip()
            metadata_dict[key.strip()] = value

    # Add a key for filename for linking
    metadata_dict['filename'] = blob_name.split('/')[-1].split('.')[0]
    try:
        metadata_dict['url'] = os.path.join(metadata_dict['type'], metadata_dict['filename'])
    except:
        print(f"Error parsing metadata for {blob_name}")

    return metadata_dict

def get_random_page():
    feed = db.collection('feed').document('content-log')
    data = feed.get().to_dict()
    random_page = choice(list(data.keys()))
    url = data[random_page]['url']

    return url

def get_feed(filters={}, page=1):
    """Get a page of the feed from Firestore
    Filters is a dictionary of filters to be applied to the feed based on doc metadata"""
    # Get the feed from Firestore
    feed = db.collection('feed').document('content-log')
    data = feed.get().to_dict()

    # Sort by key (timestamp) desc
    # Order is not guaranteed in Firestore so we need to sort it here
    data = dict(sorted(data.items(), key=lambda item: item[0], reverse=True))

    # Loop over the data and filter it
    start = (page-1)*ITEMS_PER_PAGE
    end = page*ITEMS_PER_PAGE
    feed = []
    feed_length = 0
    feed_index = 0
    for k, v in data.items():
        # Filters should contain a key (metadata value) and a list of possible values
        pass_filter = True
        for key, values in filters.items():
            # Tags are a list so we need to check if all the values are in the tags
            # We want at least ONE tag to be in the tags
            if key == 'tags':
                tags = clean_tags(v[key])
                if not any(tag in values for tag in tags):
                    pass_filter = False
                    break
            elif key == 'collection':
                # Process the collection name
                clean_collection_name = strip_punctuation(v[key]).replace(' ', '_').lower()
                if clean_collection_name not in values:
                    pass_filter = False
                    break
            elif v[key] not in values:
                pass_filter = False
                break

        if pass_filter:
            feed_index += 1
            if feed_index > start and feed_index <= end:
                feed_length += 1
                # Clean tags
                if 'tags' in v:
                    v['tags'] = clean_tags(v['tags'])
                v['clean_collection'] = strip_punctuation(v['collection']).replace(' ', '_').lower()
                feed.append(v)
                feed[-1]['date'] = k

    # Feed index contains the number of items that pass the filter
    num_pages = feed_index // ITEMS_PER_PAGE
    num_pages += 1 if feed_index % ITEMS_PER_PAGE else 0


    return {
        'feed': feed,
        'pagination': {
            'page_count': num_pages,
            'has_next': page < num_pages,
            'has_prev': page > 1,
            'prev_num': page-1,
            'next_num': page+1,
            'page': page
        }
    }

# Data routes
@app.route('/assets/images/<img_name>')
def serve_image(img_name):
    try:
        blob = get_blob('images', img_name)

        # Use send_file to send the image file directly
        img_bytes = blob.download_as_bytes()
        img_file = BytesIO(img_bytes)
        img_file.seek(0)
        return send_file(img_file, mimetype=blob.content_type)
    except Exception as e:
        abort(500, e)

@app.route('/assets/music/<filename>')
def get_music(filename):
    blob = get_blob('music', filename)

    # Load blob to get the size
    blob.reload()

    file_size = blob.size
    print(f"File size: {file_size}")

    # Partial content handling
    range_header = request.headers.get('Range', None)
    if not range_header:
        return Response(
            blob.download_as_bytes(),
            200,
            mimetype='audio/mpeg',
            headers={'Content-Length': str(file_size)}
        )

    byte_range = range_header.strip().split('=')[1]
    byte_range = byte_range.split('-')
    start = int(byte_range[0])
    end = int(byte_range[1]) if byte_range[1] else file_size - 1

    if start >= file_size or end >= file_size:
        abort(416)

    chunk = blob.download_as_bytes(start=start, end=end + 1)
    response = Response(
        chunk,
        206,
        mimetype='audio/mpeg',
        headers={
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(end - start + 1),
        }
    )
    return response

# Content routes
@app.route('/<content_type>/<content_name>')
def content(content_type, content_name):
    blob = get_blob(content_type, content_name + '.md')

    # Any special handling for music or video etc
    content = None
    tracks = None
    video_id = None
    if content_type == 'music':
        data = parse_music(blob)
        content = data['content']
        metadata = data['metadata']
        tracks = data['track_listing']
    elif content_type == 'video':
        metadata, video_id = parse_markdown(blob)
        video_id = video_id.replace('<p>', '').replace('</p>', '').strip()
    else:
        metadata, content = parse_markdown(blob)

    # Use this to get the correct template
    if not router.get(content_type):
        abort(404)

    # Register a hit
    register_hit(content_type, content_name)

    # Create our kwargs for the template
    kwargs = {
        'content': content,
        'og_tags': get_og_tags(metadata),
        'title': metadata['title'],
        'date': metadata['date'],
        'type': content_type,
        'collection': metadata['collection'],
        'navigation': get_collection_navigation(metadata, blob.name),
        'recommendations': get_recommendations(blob.name),
        'description': metadata.get('description', None),
        'video_id': metadata.get('video_id', None),
        'cover_art': metadata.get('og_image', None),
        'game_link': metadata.get('game_link', None),
        'album_art': metadata.get('og_image', None),
        'tracks': tracks,
        'hover_text': metadata.get('hover_text', None),
    }

    return render_template(router[content_type], **kwargs)


# Static routes
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    tags = request.args.get('tags', None)
    content_type = request.args.get('type', None)
    collection = request.args.get('collection', None)

    register_hit('homepage', 'index')

    # Split them on commas
    tags = tags.split(',') if tags else None
    content_type = content_type.split(',') if content_type else None
    collection = collection.split(',') if collection else None

    # Clean collection names (shouldn't need to do this because we construct the GET request ourselves but just in case)
    collection = [c.lower() for c in collection] if collection else None


    # Create a filter dictionary
    filters = {
        k: v for k, v in {
            'tags': tags,
            'type': content_type,
            'collection': collection
        }.items() if v
    }
    # Get the first page of the feed
    feed_dict = get_feed(filters=filters, page=page)
    feed = feed_dict['feed']
    pagination = feed_dict['pagination']
    og_tags = {
        'og:title': 'Edward Atkin\'s Homepage',
        'og:description': 'The personal website of Edward Atkin',
        'og:type': 'website',
        'og:image': '/assets/images/edwardatkin.jpg'
    }
    return render_template('index.html', feed=feed, pagination=pagination, og_tags=og_tags)

# Static routes for misc docs like about, browse by collection, etc
@app.route('/<doc>')
def about(doc):
    blob = get_blob('', f'{doc}.md')

    register_hit('homepage', doc)

    _, content = parse_markdown(blob)
    og_tags = {
        'og:title': 'Edward Atkin\'s Homepage',
        'og:description': 'The personal website of Edward Atkin',
        'og:type': 'website',
        'og:image': '/assets/images/edwardatkin.jpg'
    }
    return render_template('misc_doc.html', content=content, og_tags=og_tags)

@app.route('/random')
def random():
    register_hit('homepage', 'random')

    url = get_random_page()
    # Redirect
    return redirect(url)

@app.route('/login')
def login_get():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return '', 204

@app.route('/admin')
@login_required
def admin():
    return "Hello this is the admin panel lol!"

@app.route('/auth/login', methods=['POST'])
@limiter.limit('5 per hour')
def login_post():
    email = request.form['username']
    password = request.form['password']

    try:
        user = auth.sign_in_with_email_and_password(email, password)
        session['user'] = user
        return redirect(url_for('admin'))
    except Exception as e:
        print(e)
        logging.error(e)
        return redirect(url_for('index'))

# RSS
@app.route('/rss')
def rss():
    base_url = os.environ.get('BASE_URL', 'https://homepage-mkmtu6ld5q-nw.a.run.app/')

    feed = FeedGenerator()
    feed.id(base_url)
    feed.title('Edward Atkin\'s Homepage')
    feed.link(href=base_url, rel='alternate')
    feed.description('The personal website of Edward Atkin')
    feed.language('en')
    feed.ttl(3600)

    # Get the feed from Firestore
    data = db.collection('feed').document('content-log').get().to_dict()
    # Sort
    data = dict(sorted(data.items(), key=lambda item: item[0], reverse=True))

    # Get the latest date for the feed last build date
    latest_date = list(data.keys())[0]
    # Parse it
    latest_date = dt.strptime(latest_date, "%Y-%m-%d %H:%M:%S")
    # Timezone
    latest_date = pytz.timezone('Europe/London').localize(latest_date)

    # Now set the last build date
    feed.lastBuildDate(latest_date)

    num_items = 10

    # Feedgen expects oldest first so we need to reverse the data shrug emoji
    reversed_data = list(data.items())[:num_items][::-1]

    for date, v in reversed_data:
        # Create an entry for each item in the feed
        entry = feed.add_entry()
        entry.id(f'{base_url}{v["url"]}')
        entry.title(v['title'])
        entry.link(href=f'{base_url}{v["url"]}', rel='alternate')
        entry.description(v['description'])
        pub_date = dt.strptime(date, "%Y-%m-%d %H:%M:%S")
        # Localise to London
        pub_date = pytz.timezone('Europe/London').localize(pub_date)
        entry.pubDate(pub_date)

        if 'og_image' in v:
            # Ext should be jpg or png - get mimetype from the extension
            ext = v['og_image'].split('.')[-1]
            mime_type = f'image/{ext}'.lower()
            # If it says jpg then it should be jpeg
            if ext.lower() == 'jpg':
                mime_type = 'image/jpeg'
            entry.enclosure(f'{base_url[:-1]}{v["og_image"]}', 0, mime_type)

    return Response(
        feed.rss_str(pretty=True),
        mimetype='application/rss+xml'
    )



if __name__ == '__main__':
    app.run()
