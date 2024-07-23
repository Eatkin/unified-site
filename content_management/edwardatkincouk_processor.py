# Tagging utility for a bunch of old blog posts I scraped
import os

files = os.listdir(os.path.join('STAGING', 'blogs'))
files = [os.path.join('STAGING', 'blogs', f) for f in files]

for f in files:
    # Open it
    with open(f, 'r') as file_content:
        content = file_content.read()

    _, metadata, content = content.split('---', 2)
    metadata_dict = {}
    for line in metadata.strip().split('\n'):
        key, value = line.strip().split(': ', 1)
        metadata_dict[key] = value

    tag_options = [
        ['Indie Game', 'Review', 'Archive'],
        ['Game Development', 'Devlog', 'Indie Game', 'Archive'],
        ['Video Game', 'Review', 'Archive']
    ]

    collection_options = [
        'Indie Game Reviews',
        'Video Game Reviews',
        'Devlogs',
        'Guest Blogs',
    ]

    tag_set = ''
    collection_set = ''

    while True:
        print('Choose tag set for', metadata_dict['title'])
        for i, tags in enumerate(tag_options, 1):
            print(i, tags)

        choice = input("Enter your choice: ")
        choice = int(choice)
        if choice in list(range(1, len(tags) + 1)):
            tag_set = tag_options[int(choice - 1)]
            break


    while True:
        print('Choose collection for', metadata_dict['title'])
        for i, collection in enumerate(collection_options, 1):
            print(i, collection)

        choice = input("Enter your choice: ")
        choice = int(choice)
        if choice in list(range(1, len(collection_options) + 1)):
            collection_set = collection_options[int(choice - 1)]
            break

    metadata_dict['tags'] = tag_set
    metadata_dict['collection'] = collection_set

    # Write back
    metadata = '\n'.join([f"{k}: {v}" for k, v in metadata_dict.items()])

    new_content = '---\n' + metadata.strip() + '\n---\n' + content.strip()

    with open(f, 'w') as file_content:
        file_content.write(new_content)

    print("Written file", f)

print("All done thanks boss")
