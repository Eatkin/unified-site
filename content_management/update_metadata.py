# Update the metadata for all the content in the content log
import os
from google.cloud import storage
from firebase_admin import firestore, initialize_app

# Establish a connection to the Google Cloud Storage and Firestore
storage_client = storage.Client()
bucket = storage_client.bucket('website-content12345')
initialize_app()
db = firestore.client()

def get_content_log():
    global db
    content_log_ref = db.collection('feed').document('content-log')
    return content_log_ref

def get_metadata(blob_path):
    blob = bucket.blob(blob_path)
    md = blob.download_as_string().decode('utf-8')
    # We can capture the section between --- and --- and use it as metadata
    metadata = md.split('---')[1]

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
    metadata_dict['filename'] = blob_path.split('/')[-1].split('.')[0]
    try:
        metadata_dict['url'] = os.path.join(metadata_dict['type'], metadata_dict['filename'])
    except:
        print(f"Error parsing metadata for {blob}")

    return metadata_dict

def update_metadata():
    global bucket
    try:
        # So we get the content log
        content_log = get_content_log()
        content_log_data = content_log.get().to_dict()

        for v in content_log_data.values():
            # Get the metadata for the blob
            blob_path = v['location']
            metadata = get_metadata(blob_path)

            # Now update v
            v.update(metadata)

            print('Got metadata for', blob_path)

        # Write it back
        content_log.set(content_log_data)
        return True
    except Exception as e:
        return str(e)

if __name__ == '__main__':
    res = update_metadata()
    if res:
        print('Metadata updated successfully')
    else:
        print(res)
