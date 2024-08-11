import os
import re
import subprocess
from shutil import copy
from datetime import datetime as dt
from content_management.thumbnailify import generate_thumbnail
from content_management.generate_recommendations import main as generate_recommendations
from utils.string_utils import strip_punctuation
from firebase_admin import firestore, initialize_app

# global env is overwriting our local google application credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service_account.json"

initialize_app()
db = firestore.client()

# Compile re patterns
img_pattern = re.compile(r"/assets/(images/.*?)\s|$")
music_pattern = re.compile(r"/assets/(music/.*?)\s|$")

def get_site_update():
    # Find all the new content
    new_content = []
    for root, dirs, files in os.walk("STAGING"):
        # Ignore the wip folder
        if 'wip' in root:
            continue
        for file in files:
            if file.endswith(".md"):
                new_content.append(os.path.join(root, file))

    return new_content

def parse_markdown(docs):
    # Create our dictionary
    doc_metadata = {}
    for doc in docs:
        with open(doc, 'r') as f:
            doc_content = f.read()
        _, metadata, content = doc_content.split("---", 2)

        metadata_dict = {}
        for line in metadata.split("\n"):
            if line:
                key, value = line.split(":")
                metadata_dict[key] = value.strip()

        # Get the related media
        related_media = get_related_media(content)
        metadata_dict["related_media"] = related_media
        doc_metadata[doc] = metadata_dict

    return doc_metadata

def get_related_media(doc_content):
    # Find all the images in the markdown
    images = img_pattern.findall(doc_content)
    tracks = music_pattern.findall(doc_content)
    return images + tracks

def generate_thumbnails(doc_metadata):
    for metadata in doc_metadata.values():
        # Check if there is a thumbnail
        if "thumbnail" in metadata:
            # Get the thumbnail base name
            thumbnail = metadata["thumbnail"]
            base_name = thumbnail.replace("_thumbnail.jpg", ".jpg")

            possible_extensions = [".jpg", ".jpeg", ".png"]

            # Find our base image
            base_image = None
            for ext in possible_extensions:
                if os.path.exists(os.path.join("STAGING", "images", base_name + ext)):
                    base_image = os.path.join("STAGING", "images", base_name + ext)
                    break
            else:
                # If we didn't find the image, we can't generate a thumbnail
                continue

            # Generate the thumbnail
            generate_thumbnail(base_image)

def upload_content(content):
    cwd = os.getcwd()
    for doc in content:
        # Move the file to the content bucket
        # Truncate the path
        doc = doc.replace(cwd, "")
        subprocess.run(["gsutil", "cp", doc, "gs://website-content12345"])

def update_firestore(docs_metadata):
    feed_ref = db.collection('feed').document('content-log')
    feed_dict = feed_ref.get().to_dict()

    for doc, metadata in docs_metadata.items():
        # Get the edit date
        edit_date = os.path.getmtime(doc)
        edit_date = dt.fromtimestamp(edit_date).strftime("%Y-%m-%d %H:%M:%S")

        # Remove the related media from the metadata so we can update the firestore doc
        metadata_copy = metadata.copy()
        metadata_copy.pop("related_media")
        feed_dict[edit_date] = metadata_copy

        # Get the collection
        collection = metadata["collection"]
        collection = strip_punctuation(collection)

        collection_ref = db.collection("collections").document(collection)
        collection_dict = collection_ref.get().to_dict()
        collection_dict['content'].append(doc.split("/")[-1])

        collection_ref.set(collection_dict)

    feed_ref.set(feed_dict)

def move_files(doc_metadata):
    for doc, metadata in doc_metadata.items():
        # Move the file from STAGING to CONTENT
        copy(doc, doc.replace("STAGING", "CONTENT"))
        print(f"Moved {doc} to CONTENT")
        # Now move the related media
        related_media = metadata["related_media"]
        for media in related_media:
            media_path = os.path.join("STAGING", media)
            copy(media_path, media_path.replace("STAGING", "CONTENT"))
            print(f"Moved {media_path} to CONTENT")


if __name__ == "__main__":
    print("This hasn't been tested yet so please debug it before allowing it to upload, move files, and update firestore, etc")

    exit()

    content = get_site_update()

    doc_metadata = parse_markdown(content)

    generate_thumbnails(doc_metadata)

    # Upload docs to the content bucket
    upload_content(content)

    # Upload images to the content bucket
    for metadata in doc_metadata.values():
        related_media = metadata["related_media"]
        for media in related_media:
            media_type = media.split("/")[0]
            subprocess.run(["gsutil", "cp", os.path.join("STAGING", media), f"gs://website-content12345/{media_type}"])

    # Update the firestore docs
    update_firestore(doc_metadata)

    move_files(doc_metadata)

    # Generate recommendations
    generate_recommendations()
