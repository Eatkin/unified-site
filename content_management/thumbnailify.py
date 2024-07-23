# Gets all staging images and creates thumbnails for them if they don't already exist

import os
from PIL import Image

imgs = [os.path.join('STAGING', 'images', f) for f in os.listdir('STAGING/images')]

for img in imgs:
    filename = img.split('/')[-1]
    no_ext = os.path.splitext(filename)[0]
    thumbnail_name = no_ext + '_thumbnail.jpg'
    if thumbnail_name in imgs:
        continue

    im = Image.open(img)
    im.thumbnail((256, 256))
    im = im.convert('RGB')

    im.save(os.path.join('STAGING', 'images', thumbnail_name), 'JPEG')

    print(f'Created thumbnail for {filename}')
