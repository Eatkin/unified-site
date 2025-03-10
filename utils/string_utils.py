import string
import os

# Remove _ from string.puncuation
string.punctuation = string.punctuation.replace('_', '')

def strip_punctuation(s):
    return s.translate(str.maketrans('', '', string.punctuation))

def clean_tags(tags):
    """Clean a tag string"""
    return [strip_punctuation(tag).strip().lower().replace(' ', '-') for tag in tags.split(',')]

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
