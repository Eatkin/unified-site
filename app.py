import os
import logging
from random import choice, choices, shuffle
from io import BytesIO
from datetime import datetime as dt
from functools import wraps

import pytz
from flask import Flask, render_template, send_file, abort, request, redirect, Response, url_for, session
from feedgen.feed import FeedGenerator
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from utils.common import (
    ITEMS_PER_PAGE,
    CONTENT_TYPES,
    ROUTER,
    BUCKET,
    DB
)
from utils.general import register_hit, get_blob, parse_from_blob
from utils.md_parser import markdown_parser
from utils.string_utils import strip_punctuation, parse_metadata
from routing import setup_routing
from data_routes import setup_data_routes
from api import (
    setup_api,
    get_filtered_feed,
    get_ranked_recommendations
)

app = Flask(__name__)

@app.before_request
def block_php_requests():
    if request.path.lower().endswith(".php"):
        abort(404)

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
)

setup_routing(app)
setup_api(app)
setup_data_routes(app)

app.secret_key = os.environ.get('APP_SECRET_KEY')


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
    data = DB.collection('collections').document(collection).get().to_dict()
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
    recs = get_ranked_recommendations(blob_name)
    feed = get_filtered_feed()

    try:
        # Recomendations are the 'location' key of feed
        detailed_recs = []
        for item in feed:
            if item['location'] in recs:
                detailed_recs.append(item)

        num_random_pages = 3
        # Randomly select pages that are NOT in the recommendations
        random_pages = []
        while len(random_pages) < num_random_pages:
            random_page = choice(feed)
            if random_page not in detailed_recs:
                random_pages.append(random_page)

        detailed_recs.extend(random_pages)

        # Format the urls
        for page in detailed_recs:
            arg = page['url'].split('/')[-1]
            page['url'] = url_for('content', content_type=page['type'], content_name=arg)

        return detailed_recs
    except Exception as e:
        logging.error(e)
        return None


def get_og_tags(metadata):
    """Get Open Graph tags from metadata"""
    # Get the Open Graph tags from a metadata dictionary
    og_tags = {}
    for tags in ['og_title', 'og_description', 'og_image', 'og_type']:
        if tags in metadata:
            og_tags[tags.replace('og_', 'og:')] = metadata[tags]
    return og_tags if og_tags else None

def get_random_page():
    feed = get_filtered_feed()
    random_page = choice(feed)
    url = random_page['url']
    return url

def get_pagination_info(page, feed):
    """Get pagination info for a feed"""
    num_pages = len(feed) // ITEMS_PER_PAGE
    num_pages += 1 if len(feed) % ITEMS_PER_PAGE else 0

    return {
        'page_count': num_pages,
        'has_next': page < num_pages,
        'has_prev': page > 1,
        'prev_num': page-1,
        'next_num': page+1,
        'page': page
    }

# Content routes
@limiter.limit('10 per minute')
@app.route('/<content_type>/<content_name>')
def content(content_type, content_name):
    blob = get_blob(content_type, content_name + '.md')

    # Any special handling for music or video etc
    content = None
    tracks = None
    video_id = None
    if content_type == 'music':
        data = parse_music(blob)
        content = markdown_parser(data['content'])
        metadata = data['metadata']
        tracks = data['track_listing']
    elif content_type == 'video':
        data = parse_from_blob(blob)
        video_id = data['markdown']
        metadata = data['metadata']
        video_id = video_id.replace('<p>', '').replace('</p>', '').strip()
    else:
        data = parse_from_blob(blob)
        metadata = data['metadata']
        content = markdown_parser(data['markdown'])

    # Use this to get the correct template
    if not ROUTER.get(content_type):
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

    return render_template(ROUTER[content_type], **kwargs)


# Static routes
@limiter.limit('10 per minute')
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    filters = {}
    for filter in ['tags', 'type', 'collection']:
        if filter in request.args:
            filters[filter] = request.args.get(filter)

    feed = get_filtered_feed(filters)
    # This is a hack but this means there was an error
    if type(feed) == dict:
        feed = []
    pagination = get_pagination_info(page, feed)

    # Slice the feed to get the correct page
    start = (page-1)*ITEMS_PER_PAGE
    end = page*ITEMS_PER_PAGE
    feed = feed[start:end]

    register_hit('homepage', 'index')

    og_tags = {
        'og:title': 'Edward Atkin\'s Homepage',
        'og:description': 'The personal website of Edward Atkin',
        'og:type': 'website',
        'og:image': '/assets/images/edwardatkin.jpg'
    }
    return render_template('index.html', feed=feed, pagination=pagination, og_tags=og_tags)

# Static routes for misc docs like about, browse by collection, etc
@limiter.limit('10 per minute')
@app.route('/<doc>')
def about(doc):
    blob = get_blob('', f'{doc}.md')

    register_hit('homepage', doc)

    data = parse_from_blob(blob)
    content = markdown_parser(data['markdown'])
    og_tags = {
        'og:title': 'Edward Atkin\'s Homepage',
        'og:description': 'The personal website of Edward Atkin',
        'og:type': 'website',
        'og:image': '/assets/images/edwardatkin.jpg'
    }
    return render_template('misc_doc.html', content=content, og_tags=og_tags)

@limiter.limit('10 per minute')
@app.route('/random')
def random():
    register_hit('homepage', 'random')

    url = get_random_page()
    # Redirect
    return redirect(url)

# Unused auth routes I never got around to implementing and now don't need
# @app.route('/login')
# def login_get():
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.pop('user', None)
#     return '', 204

# @app.route('/admin')
# @login_required
# def admin():
#     return "Hello this is the admin panel lol!"

# @app.route('/auth/login', methods=['POST'])
# @limiter.limit('5 per hour')
# def login_post():
#     email = request.form['username']
#     password = request.form['password']

#     try:
#         user = AUTH.sign_in_with_email_and_password(email, password)
#         session['user'] = user
#         return redirect(url_for('admin'))
#     except Exception as e:
#         print(e)
#         logging.error(e)
#         return redirect(url_for('index'))

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
    data = DB.collection('feed').document('content-log').get().to_dict()
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
