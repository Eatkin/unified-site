# About

This project is a simple web application that uses Flask, Jinja2, and Markdown to render dynamic HTML pages from markdown files.

The aim of this project is to provide a universal chronological feed service that can display content from various sources in a consistent and user-friendly manner. I use this project to host my personal blog, music, and other content. It's intended to be an 'everything' feed that can display blog posts, music, comics, videos, games, and other content types in a single feed.

The project is designed to be easily extensible and customisable to suit different needs. It is built to be easily deployed on Google Cloud Platform, but can be deployed on other platforms with some minor modifications.

All content is rendered from markdown files

Routes implemented allow for:
* Blog posts
* Music albums/playlists
* Comics
* Youtube videos
* Games

## Current Status

Currently in development but the project provides a good framework for displaying content. The project is currently being used to host my personal blog and music.

This project is a work in progress and is being actively developed.

Future plans include:

* Display filtering options on the feed page
* RSS feed with filtering options
* Global navigation (currently navigation is only available within collections)
* Content management scripts for updating the database and content
* Possible admin panel for managing content within the application

My personal website may be viewed at [https://homepage-mkmtu6ld5q-nw.a.run.app/](https://homepage-mkmtu6ld5q-nw.a.run.app/).

## Project Structure

The main entry point for the application is `app.py`, which sets up the Flask application and defines the routes for rendering HTML pages.

This includes routes for serving content including images, audio files, and markdown files.

Content is coarsely sorted into content types (blog, music, etc) and then further sorted by collection (Ed's Blog, Ed's Music, etc).

Collections allow for further categorisation of content within a content type and also for navigation between different posts within a collection.

Content is stored in a Google Cloud Storage bucket and accessed via the Google Cloud Storage API.

Feed data is stored in a Firestore database and accessed via the Firestore API.

Collection data is also stored in a Firestore database and accessed via the Firestore API.

Various content management scripts are included in the content_management diretory including updating metadata from markdown files, creating thumbnails from images, etc.

## Expected Markdown Format

Markdown files are expected to follow a specific format to ensure proper rendering on the website.

Example markdown file including metadata at the beginning of the file:

```markdown
---
title: My First Blog Post
author: Ed
date: 2021-10-01
tags: ['blog', 'first post']
type: blog
thumbnail: /assets/images/first_post_thumbnail.jpg
og_title: My First Blog Post
og_description: This is my very first blog post. Welcome to my blog!
og_image: /assets/images/first_post.jpg
og_type: article
collection: Ed's Blog
---
Hello, World!

This is some blog content
```

This format varies based on the content type (blog, music, etc) and the metadata required for each type.

## Expected Firestore Document Structure

The firestore database is used to store feed data and collection data. It contains two collections: `feed` and `collections`.

### Feed Collection

This collection contains a single document 'content-log'. It is intended to contain the location of content, url (usually the same as the location with no file extension) associated metadata and a timestamp as the key. It is structured of the form:

```json
{'2023-03-05 13:30:15': {
  'location': 'blogs/blog1.md',
  'url': '/blogs/blog1',
  'metadata_key': 'some_metadata'
},
{'2023-03-05 13:30:15': {
  'location': 'music/album1.md',
  'url': /music/album1',
  'metadata_key': 'some_metadata'
}
}
```

### Collections Collection

This contains a document for each collection. Collection names are lowercased, with punctuation stripped and spaces replaced with underscores, for example "Ed's Blog" become "eds_blog".

Each document contains a single key 'content' and a list of markdown documents in chronological order. Example:

  ```json
  {
    'content': [
      'blog1.md',
      'blog2.md',
      'blog3.md'
    ]
  }
  ```

It is important to note that collection are expected to all be of the same content type (blog, music, etc) so the filenames are routed correctly. E.g.  blog1.md will have navigation options at the bottom leading to the /blogs/blog2 and /blogs/blog3 pages. This is inferred from the filename provided in the collection.

## Specifications for Content Types

### Bucket Format

Content is stored in a Google Cloud Storage bucket with the following structure:

```
├── blogs
|   ├── blog1.md
|   └── blog2.md
├── images
|   ├── image1.png
|   └── thumbnail.jpg
└── music
    ├── album1.md
    ├── song1.mp3
    └── song2.mp3
```

### Blog

Blog posts provide the basis for what metadata is expected for other content types. Only additional metadata for other content types will be listed.

Blog posts are expected to have the following metadata:
* title
* author
* date
* tags
* description
* type
* thumbnail (OPTIONAL)
* og_title (OPTIONAL)
* og_description (OPTIONAL)
* og_image (OPTIONAL)
* og_type (OPTIONAL)
* collection

### Comic

Comics are identical to blog posts but with the additional metadata:
* hover_text (OPTIONAL)

### Music

Music pages are identical to blog posts but with the additional metadata:
* album_art (OPTIONAL)

In addition to the metadata, music posts are expected to have a list of songs with the following format:

```markdown
---
title: Song Title
additional metadata
---
Page content
---
title: Song Title
file: /assets/music/song.mp3
title: Song Title 2
file: /assets/music/song2.mp3
...
```

### Games

Games also contain the additional metadata:
* game_link

This provides a link to where the game may be downloaded/played.

### Video

Video documents provide a link to a youtube video. The body of the markdown file should be a single line containing the youtube video ID which will be embedded in the page.

### Project

Projects are identical to blog posts but use a separate route.

## Data Routes

### /Assets/images/<img_name>

This route serves images from the Google Cloud Storage bucket. Images are expected to be stored in the `images` directory. Images are served as a BytesIO object.

### /Assets/music/<music_name>

This route serves partial content of music files from the Google Cloud Storage bucket. Music files are expected to be stored in the `music` directory. Music files are served as a BytesIO object.

## Additional Routes and Features

### Random Page

A random page can be accessed by visiting `/random`.

### Filtering

Filters may be passed into the feed via url parameters. For example, to filter by tag, the feed url may have `?tag=first post` appended will only display blog posts with the tag 'first post'.

### Music Player

A music player is included on music pages that allows for the playing of music files. This is managed through javascript with the script located in `static/js/music_player.js`.

The music player is a simple HTML5 audio player with custom controls and styling.


## Running the Application

### Requirements

Project was built using Python 3.10.6.

All requirements are listed in `requirements.txt` and can be installed using the following command:

```bash
pip install -r requirements.txt
```

### Running the Application

Once the project is set up, you can run the application using the following command:

```bash
flask run
```

In addition there are two makefile commands that can be used to run and stop the application:

```bash
make run
```

```bash
make stop
```

These commands will start and stop the application in a tmux session so that the application can be run in the background.

## Extending and Altering the Application

This application was built to serve my personal needs, but it can be easily extended to serve other purposes.

It may also be altered to source content from different locations or to render content in different ways. The `get_blob` function in `app.py` is responsible for fetching content from the Google Cloud Storage bucket, so may easily be altered to fetch content from a different location such as a local directory or a different cloud storage bucket.

This requires some minor modifications to some functions that require the content to be passed in as a blob object.

New routes may easily be added to the application in a similar format to existing content routes to render new content types or to render content in different ways.
