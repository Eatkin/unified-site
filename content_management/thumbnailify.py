# Gets all staging images and creates thumbnails for them if they don't already exist

import os
from PIL import Image

def generate_thumbnail(img):
    path, filename = os.path.split(img)
    no_ext = os.path.splitext(filename)[0]
    thumbnail_name = no_ext + '_thumbnail.jpg'

    if os.path.exists(os.path.join(path, thumbnail_name)):
        print(f'Thumbnail already exists for {filename}')
        return

    im = Image.open(img)
    im.thumbnail((256, 256))
    im = im.convert('RGB')

    im.save(os.path.join('STAGING', 'images', thumbnail_name), 'JPEG')

    print(f'Created thumbnail for {filename}')

if __name__ == "__main__":
    imgs = [os.path.join('STAGING', 'images', f) for f in os.listdir('STAGING/images')]
    for img in imgs:
        generate_thumbnail(img)
