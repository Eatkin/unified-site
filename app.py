import os
from io import BytesIO

from flask import Flask, render_template, send_file, abort
from google.cloud import storage
from firebase_admin import firestore, initialize_app
import marko

# Establish a connection to the Google Cloud Storage and Firestore
storage_client = storage.Client()
bucket = storage_client.bucket('website-content12345')
initialize_app()
db = firestore.client()

# Globals
ITEMS_PER_PAGE = 10

app = Flask(__name__)

def get_blob(blob_type, name):
    print("Path: ", os.path.join(blob_type, name))
    blob = bucket.blob(os.path.join(blob_type, name) + ".md")
    if not blob.exists():
        print("Blob does not exist")
        abort(404)
    return blob

def parse_markdown(blob):
    # Parse the markdown content into metadata and content
    md = blob.download_as_string().decode('utf-8')
    # We can capture the section between --- and --- and use it as metadata
    metadata = md.split('---')[1]
    metadata = parse_metadata(metadata, blob.name)
    content = md.split('---')[2]
    content = marko.convert(content)

    return metadata, content

def get_og_tags(metadata):
    # Get the Open Graph tags from a metadata dictionary
    og_tags = {}
    for tags in ['og_title', 'og_description', 'og_image']:
        if tags in metadata:
            og_tags[tags.replace('og_', 'og:')] = metadata[tags]
    return og_tags if og_tags else None

def parse_metadata(metadata, blob_name):
    # Parse the metadata section of the markdown file and return a dictionary
    metadata_dict = {}
    for line in metadata.split('\n'):
        if line:
            split_line = line.split(':')
            key = split_line[0].strip()
            # Remove the quotes
            value = ":".join(split_line[1:]).strip()[1:-1]
            metadata_dict[key.strip()] = value

    # Add a key for filename for linking
    metadata_dict['filename'] = blob_name.split('/')[-1].split('.')[0]
    metadata_dict['url'] = os.path.join(metadata_dict['type'], metadata_dict['filename'])

    return metadata_dict

def get_description(blob):
    # Get the description from a markdown blob for the feed
    md = blob.download_as_string().decode('utf-8')
    # We can capture the section between --- and --- and use it as metadata
    metadata = md.split('---')[1]

    description = parse_metadata(metadata, blob.name)
    return description

def get_feed(page=1):
    # Get the feed from Firestore
    feed = db.collection('feed').document('content-log')
    data = feed.get().to_dict()

    # Sort by key (timestamp) desc
    data = dict(sorted(data.items(), key=lambda item: item[0], reverse=True))

    # Select keys for pagination
    start = (page-1)*ITEMS_PER_PAGE
    end = page*ITEMS_PER_PAGE+1
    page_keys = list(data.keys())[start:end]

    data = {k: v for k, v in data.items() if k in page_keys}

    feed = []

    # Go through these, get description from location and replace the value with the description returned
    for key, value in data.items():
        blob = bucket.blob(value['location'])
        feed.append(get_description(blob))

    return feed

# Data routes
@app.route('/assets/images/<img_name>')
def serve_image(img_name):
    try:
        # Strip the images/ prefix if it exists
        blob = bucket.blob(os.path.join("images", img_name))
        # Ensure the blob exists before attempting to serve it
        if not blob.exists():
            abort(404)

        # Use send_file to send the image file directly
        img_bytes = blob.download_as_bytes()
        img_file = BytesIO(img_bytes)
        return send_file(img_file, mimetype=blob.content_type)
    except Exception as e:
        abort(500, e)

@app.route('/')
def index():
    # Get the first page of the feed
    feed = get_feed()
    return render_template('index.html', feed=feed)

# Content routes
@app.route('/blog/<blog_name>')
def blog(blog_name):
    # We want to get the markdown content, render it and pass the html to the template
    blob = get_blob('blogs', blog_name)
    metadata, content = parse_markdown(blob)
    og_tags = get_og_tags(metadata)

    # Render blog template
    return render_template('blog.html', content=content, og_tags=og_tags)



if __name__ == '__main__':
    app.run()
