import os
import json
from io import BytesIO

from flask import Flask, render_template, send_file, abort, request
from google.cloud import storage
from firebase_admin import firestore, initialize_app

from utils.md_parser import markdown_parser
from utils.string_utils import strip_punctuation

# Establish a connection to the Google Cloud Storage and Firestore
storage_client = storage.Client()
bucket = storage_client.bucket('website-content12345')
initialize_app()
db = firestore.client()

# Globals
ITEMS_PER_PAGE = 10

app = Flask(__name__)

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error=error), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error=error), 500

def get_blob(blob_type, name):
    """Get a blob from Google Cloud Storage or abort with a 404 if not found"""
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
    metadata = md.split('---')[1]
    metadata = parse_metadata(metadata, blob.name)
    content = md.split('---')[2]
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
        return send_file(img_file, mimetype=blob.content_type)
    except Exception as e:
        abort(500, e)

@app.route('/assets/music/<filename>')
def get_music(filename):
    try:
        blob = get_blob('music', filename)
        audio_bytes = blob.download_as_bytes()
        audio_stream = BytesIO(audio_bytes)
        return send_file(audio_stream, mimetype=blob.content_type)
    except Exception as e:
        abort(500, e)

# Content routes
@app.route('/project/<project_name>')
def project(project_name):
    blob = get_blob('projects', project_name + '.md')
    metadata, content = parse_markdown(blob)
    og_tags = get_og_tags(metadata)

    # get title and date from the metadata
    title = metadata['title']
    date = metadata['date']
    collection = metadata['collection']

    # get the navigation for the collection
    navigation = get_collection_navigation(metadata, blob.name)

    # render project template
    return render_template('project.html', content=content, og_tags=og_tags, title=title, date=date, navigation=navigation, collection=collection)

@app.route('/blog/<blog_name>')
def blog(blog_name):
    # we want to get the markdown content, render it and pass the html to the template
    blob = get_blob('blogs', blog_name + '.md')

    metadata, content = parse_markdown(blob)
    og_tags = get_og_tags(metadata)

    # get title and date from the metadata
    title = metadata['title']
    date = metadata['date']
    collection = metadata['collection']

    # get the navigation for the collection
    navigation = get_collection_navigation(metadata, blob.name)

    # render blog template
    return render_template('blog.html', content=content, og_tags=og_tags, title=title, date=date, navigation=navigation, collection=collection)

@app.route('/comic/<comic_name>')
def comic(comic_name):
    # Very similar to blog but uses an alternative template
    blob = get_blob('comics', comic_name + '.md')
    metadata, content = parse_markdown(blob)
    og_tags = get_og_tags(metadata)

    # Get title and date from the metadata
    title = metadata['title']
    date = metadata['date']
    description = metadata['description']
    collection = metadata['collection']

    # Get the navigation for the collection
    navigation = get_collection_navigation(metadata, blob.name)
    hover_text = metadata['hover_text'] if 'hover_text' in metadata else None

    # Add hover text to images
    if hover_text:
        content = content.replace('<img', f'<img title="{hover_text}"')

    # Render blog template
    return render_template('comic.html', content=content, og_tags=og_tags, title=title, date=date, navigation=navigation, collection=collection, description=description)

@app.route('/music/<collection_name>')
def music(collection_name):
    # Get the music collection
    blob = get_blob('music', collection_name + '.md')

    data = parse_music(blob)

    og_tags = get_og_tags(data['metadata'])
    title = data['metadata']['title']
    content = data['content']
    tracks = data['track_listing']
    album_art = data['metadata']['og_image']
    collection = data['metadata']['collection']

    navigation = get_collection_navigation(data['metadata'], blob.name)

    # Render music template
    return render_template('music.html', content=content, og_tags=og_tags, title=title, tracks=tracks, album_art=album_art, navigation=navigation, collection=collection)

@app.route('/video/<video_name>')
def video(video_name):
    # Get the video content
    blob = get_blob('videos', video_name + '.md')

    metadata, video_id = parse_markdown(blob)
    # Strip html tags from the video_id
    video_id = video_id.replace('<p>', '').replace('</p>', '').strip()
    og_tags = get_og_tags(metadata)

    # Get title and date from the metadata
    title = metadata['title']
    date = metadata['date']
    collection = metadata['collection']
    description = metadata['description']

    # Get the navigation for the collection
    navigation = get_collection_navigation(metadata, blob.name)

    # Render blog template
    return render_template('video.html', video_id=video_id, description=description, og_tags=og_tags, title=title, date=date, navigation=navigation, collection=collection)

@app.route('/game/<game_name>')
def game(game_name):
    # we want to get the markdown content, render it and pass the html to the template
    blob = get_blob('games', game_name + '.md')
    metadata, content = parse_markdown(blob)
    og_tags = get_og_tags(metadata)

    # get title and date from the metadata
    title = metadata['title']
    date = metadata['date']
    collection = metadata['collection']
    cover_art = metadata['og_image']
    game_link = metadata['game_link']

    # get the navigation for the collection
    navigation = get_collection_navigation(metadata, blob.name)

    # render blog template
    return render_template('game.html', content=content, og_tags=og_tags, title=title, date=date, navigation=navigation, collection=collection, cover_art=cover_art, game_link=game_link)



@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    tags = request.args.get('tags', None)
    content_type = request.args.get('type', None)
    collection = request.args.get('collection', None)

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
    return render_template('index.html', feed=feed, pagination=pagination)



if __name__ == '__main__':
    app.run()
