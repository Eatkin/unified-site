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

try:
    initialize_app()
except:
    pass
db = firestore.client()

# Compile re patterns - these capture the relative path to the media
img_pattern = re.compile(r"/assets/(images/[\S]+)")
music_pattern = re.compile(r"/assets/(music/[\S]+)")

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
        related_media = get_related_media(doc_content)
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
            base_name = thumbnail.replace("_thumbnail.jpg", "")
            base_name = base_name.split("/")[-1]

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
        # Get the subdirectory
        subdirectory = doc.split("/")[1]
        subprocess.run(["gsutil", "cp", doc, f"gs://website-content54321/{subdirectory}"])

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
        metadata_copy['url'] = os.path.join(metadata_copy['type'], doc.split("/")[-1].split(".")[0])
        metadata_copy['location'] = doc.replace("STAGING", "")
        feed_dict[edit_date] = metadata_copy

        print("Edit date:", edit_date)
        print(f"Updating firestore with {metadata_copy}")

        # Get the collection
        collection = metadata["collection"]
        collection = strip_punctuation(collection)
        collection = collection.replace(" ", "_").lower()

        collection_ref = db.collection("collections").document(collection)
        collection_dict = collection_ref.get().to_dict()
        collection_dict['content'].append(doc.split("/")[-1])

        print(collection_dict)

        collection_ref.set(collection_dict)

    feed_ref.set(feed_dict)

def move_files(doc_metadata):
    for doc, metadata in doc_metadata.items():
        # Move the file from STAGING to CONTENT
        copy(doc, doc.replace("STAGING", "CONTENT"))
        print(f"Copied {doc} to CONTENT")
        # Now move the related media
        related_media = metadata["related_media"]
        for media in related_media:
            media_path = os.path.join("STAGING", media)
            copy(media_path, media_path.replace("STAGING", "CONTENT"))
            print(f"Copied {media_path} to CONTENT")

def cleanup_files(doc_metadata):
    for doc, metadata in doc_metadata.items():
        # Remove the file from STAGING
        if os.path.exists(doc.replace("STAGING", "CONTENT")):
            os.remove(doc)
            print(f"Removed {doc}")
        else:
            print(f"Could not find {doc} in CONTENT, it hasn't been moved as expected")
        # Now remove the related media
        related_media = metadata["related_media"]
        for media in related_media:
            media_path = os.path.join("STAGING", media)
            if os.path.exists(media_path.replace("STAGING", "CONTENT")):
                os.remove(media_path)
                print(f"Removed {media_path}")
            else:
                print(f"Could not find {media_path} in CONTENT, it hasn't been moved as expected")


if __name__ == "__main__":
    content = get_site_update()

    print("Found the following content:")
    print(content)

    doc_metadata = parse_markdown(content)

    print("Parsed the following metadata:")
    print(doc_metadata)

    generate_thumbnails(doc_metadata)

    print("Generated thumbnails")

    # Upload docs to the content bucket
    upload_content(content)

    # Upload images to the content bucket
    for metadata in doc_metadata.values():
        related_media = metadata["related_media"]
        for media in related_media:
            media_type = media.split("/")[0]
            subprocess.run(["gsutil", "cp", os.path.join("STAGING", media), f"gs://website-content54321/{media_type}"])

    # Update the firestore docs
    update_firestore(doc_metadata)

    # Generate recommendations
    generate_recommendations()

    print("Generated recommendations")

    move_files(doc_metadata)

    cleanup_files(doc_metadata)

    print("Finished updating the site")
