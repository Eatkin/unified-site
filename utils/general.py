import os
from utils.common import DB, CONTENT_TYPES, BUCKET
from utils.string_utils import parse_metadata
from flask import abort

def register_hit(content_type, content_name):
    # Register a hit in our hitcounter collection
    hit_counter_ref = DB.collection('hit_counter').document('hits')
    hit_counter = hit_counter_ref.get().to_dict()
    key = os.path.join(content_type, content_name)
    if key in hit_counter:
        hit_counter[key] += 1
    else:
        hit_counter[key] = 1

    hit_counter_ref.set(hit_counter)

def get_blob(blob_type, name):
    """Get a blob from Google Cloud Storage or abort with a 404 if not found"""
    blob_type = CONTENT_TYPES.get(blob_type, blob_type)
    try:
        blob = BUCKET.blob(os.path.join(blob_type, name))
        if not blob.exists():
            print(f"Blob {name} not found")
            # Render error page
            abort(404)
        return blob
    except Exception as e:
        print(e)
        abort(500, e)

def parse_from_blob(blob):
    # Download the blob
    blob_name = blob.name
    blob = blob.download_as_string().decode('utf-8')

    # Now we just need to parse it into metadata and content
    _, metadata, content = blob.split('---', 2)
    if metadata.strip():
        metadata = parse_metadata(metadata, blob_name)
    else:
        metadata = {}
    # Now supply the metadata and content to the user
    data = {
        "metadata": metadata,
        "markdown": content
    }
    return data
