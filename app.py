import os
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

def get_blob(blob_type, name):
    """Get a blob from Google Cloud Storage or abort with a 404 if not found"""
    try:
        blob = bucket.blob(os.path.join(blob_type, name))
        if not blob.exists():
            print(f"Blob {name} not found")
            abort(404)
        return blob
    except Exception as e:
        print(e)
        abort(500, e)


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
    metadata_dict['url'] = os.path.join(metadata_dict['type'], metadata_dict['filename'])

    return metadata_dict

def get_description(blob):
    """Get the description from a markdown blob for the feed"""
    # Get the description from a markdown blob for the feed
    md = blob.download_as_string().decode('utf-8')
    # We can capture the section between --- and --- and use it as metadata
    metadata = md.split('---')[1]

    description = parse_metadata(metadata, blob.name)
    return description

def get_feed(page=1):
    """Get a page of the feed from Firestore"""
    # Get the feed from Firestore
    feed = db.collection('feed').document('content-log')
    data = feed.get().to_dict()

    # Sort by key (timestamp) desc
    # Order is not guaranteed in Firestore so we need to sort it here
    data = dict(sorted(data.items(), key=lambda item: item[0], reverse=True))

    num_pages = len(data) // ITEMS_PER_PAGE

    # Select keys for pagination
    start = (page-1)*ITEMS_PER_PAGE
    end = page*ITEMS_PER_PAGE
    page_keys = list(data.keys())[start:end]

    data = {k: v for k, v in data.items() if k in page_keys}

    feed = []

    # Go through these, get description from location and replace the value with the description returned
    for key, value in data.items():
        blob = bucket.blob(value['location'])
        feed.append(get_description(blob))

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
@app.route('/blog/<blog_name>')
def blog(blog_name):
    # We want to get the markdown content, render it and pass the html to the template
    blob = get_blob('blogs', blog_name + '.md')
    metadata, content = parse_markdown(blob)
    og_tags = get_og_tags(metadata)

    # Get title and date from the metadata
    title = metadata['title']
    date = metadata['date']
    collection = metadata['collection']

    # Get the navigation for the collection
    navigation = get_collection_navigation(metadata, blob.name)

    # Render blog template
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

    # Render music template
    return render_template('music.html', content=content, og_tags=og_tags, title=title, tracks=tracks, album_art=album_art)

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



@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    # Get the first page of the feed
    feed_dict = get_feed(page=page)
    feed = feed_dict['feed']
    pagination = feed_dict['pagination']
    return render_template('index.html', feed=feed, pagination=pagination)




if __name__ == '__main__':
    app.run()
