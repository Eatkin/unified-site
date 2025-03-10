# API endpoints for command line interface so that users don't have to visit the website
# Cause websites are for losers
import random
from collections import defaultdict
from flask import request, jsonify
from utils.common import DB, ITEMS_PER_PAGE, STORAGE_CLIENT
from utils.general import get_blob, parse_from_blob
from utils.string_utils import clean_tags, strip_punctuation

commands = [
    {
        "path": "/api/commands",
        "method": "GET",
        "description": "Returns a list of available API endpoints with usage details.",
        "params": None
    },
    {
        "path": "/api/complaints",
        "method": "POST",
        "description": "Submit a complaint and receive an unhelpful response.",
        "params": {
            "complaint": "string (Your complaint text)"
        }
    },
    {
        "path": "/api/feed",
        "method": "GET",
        "description": "Retrieve a filtered (or not, if no params are supplied) list of articles. Filters are OR conditions, not AND.",
        "params": {
            "tags": "string (Optional, comma-separated tags to filter)",
            "collection": "string (Optional, filter by collection)",
            "type": "string (Optional, filter by type)"
        }
    },
    {
        "path": "/api/latest",
        "method": "GET",
        "description": "Retrieve the latest article.",
        "params": None
    },
    {
        "path": "/api/random",
        "method": "GET",
        "description": "Retrieve a random article.",
        "params": None
    },
    {
        "path": "/api/article/<path:url>",
        "method": "GET",
        "description": "Retrieve a specific article by its URL.",
        "params": {
            "url": "string (The article url in the form type/filename)"
        }
    },
    {
        "path": "/api/recommendations",
        "method": "GET",
        "description": "Retrieve all recommendations.",
        "params": None
    },
    {
        "path": "/api/recommendations/<path:url>",
        "method": "GET",
        "description": "Retrieve recommendations for a specific article.",
        "params": {
            "url": "string (The article url in the form type/filename)"
        }
    },
    {
        "path": "/api/static-pages",
        "method": "GET",
        "description": "Retrieve all static pages.",
        "params": None
    },
    {
        "path": "/api/static-pages/<path:url>",
        "method": "GET",
        "description": "Retrieve a specific static page.",
        "params": {
            "url": "string (Page filename WITHOUT .md extension)"
        }
    },
    {
        "path": "/api/categories",
        "method": "GET",
        "description": "Retrieve all categories with article counts.",
        "params": None
    },
    {
        "path": "/api/tags",
        "method": "GET",
        "description": "Retrieve all tags with frequency counts.",
        "params": None
    },
    {
        "path": "/api/authors",
        "method": "GET",
        "description": "Retrieve all authors with article counts.",
        "params": None
    }
]

# API utility functions
def get_full_feed():
    """Get a page of the feed from Firestore
    Returns:
    feed (dict): of form {date: article}
    """
    # Get the feed from Firestore
    feed = DB.collection('feed').document('content-log')
    data = feed.get().to_dict()

    # Sort by key (timestamp) desc
    # Order is not guaranteed in Firestore so we need to sort it here
    data = dict(sorted(data.items(), key=lambda item: item[0], reverse=True))
    return data

def feed_item_matches_filter(item, filters):
    """Check if an item matches a filter
    Params:
    item (dict): The item to check
    filter (dict): The filter to apply
    Returns:
    bool: True if the item matches the filter, False otherwise
    """
    for key, values in filters.items():
        # Tags are a list so we need to check if all the values are in the tags
        # We want at least ONE tag to be in the tags
        if key == 'tags':
            tags = clean_tags(item[key])
            values = clean_tags(values)
            if not any(tag in values for tag in tags):
                return False
        elif key == 'collection':
            # Process the collection name
            clean_collection_name = strip_punctuation(item[key]).replace(' ', '_').lower()
            # Split and clean the values
            values = [strip_punctuation(v).replace(' ', '_').lower() for v in values.split(',')]
            if clean_collection_name not in values:
                return False
        elif item[key] not in values:
            return False

    return True

def get_filtered_feed(filter=None):
    """Get the feed with an optional filter applied
    Params:
    filter (dict): A dictionary of filters to apply
    Returns:
    list|dict: A list of articles that match the filter, or an error message
    """
    data = get_full_feed()

    # Clean up the data by cleaning tags and stripping punctuation from collection names
    # This also converts the data to a list of dictionaries
    filtered_data = []
    for key, item in data.items():
        if filter and not feed_item_matches_filter(item, filter):
            continue
        item['tags'] = clean_tags(item['tags'])
        item['date'] = key
        filtered_data.append(item)

    if not filtered_data:
        return {"error": "No articles found"}

    return filtered_data

def get_all_recommendations():
    return DB.collection('recommendations').document('recommendations').get().to_dict()

def get_ranked_recommendations(url):
    recommendations = get_all_recommendations()
    if url not in recommendations:
        return {"error": "No recommendations found for this article"}
    return recommendations[url]

def get_static_pages():
    # There isn't really a way to do this so I guess list blobs that match a glob pattern?
    glob_pattern = "*.md"
    blobs = STORAGE_CLIENT.list_blobs("website-content54321", match_glob=glob_pattern)
    blobs = [blob.name for blob in blobs]
    return blobs

def setup_api(app):
    @app.route('/api/commands', methods=['GET'])
    def get_commands():
        return jsonify(commands), 200

    @app.route('/api/complaints', methods=['POST'])
    def post_complaint():
        try:
            complaint = request.json.get('complaint', "No complaint provided")
        except:
            complaint = "Invalid complaint format. Learn to use JSON."
            return jsonify({"error": complaint}), 400

        if 'complaint' not in request.json:
            return jsonify({"error": "No complaint provided, learn to read the docs"}), 400

        responses = [
            "Your complaint has been noted and promptly ignored.",
            "Error 418: I'm a teapot, and I do not care.",
            "Thank you for your feedback. It will be lovingly stored in /dev/null.",
            "Your complaint has been successfully submitted to the void. The void does not care.",
            "We take your complaint very seriously. We will get back to you in 3-5 business days. Or not.",
            "Your complaint will be reviewed by our team of highly trained monkeys. They will get back to you shortly.",
            "no u",
            "Test successful. Complaints are working as intended.",
            "Thank you for your feedback. We will get back to you as soon as we care.",
        ]
        users = [
            "Some loser",
            "Some idiot",
            "A dork",
            "A nerd",
            "Fred the intern",
            "A random person",
            "Someone who doesn't matter",
            "My mom",
            "Boaty McBoatface",
            "An eejit",
        ]
        data = {
            "user": random.choice(users),
            "complaint": complaint,
            "response": random.choice(responses)
        }
        return jsonify(data), 200

    @app.route('/api/feed', methods=['GET'])
    def get_feed():
        # Get filters from query parameters
        filters = {}
        for filter in ['tags', 'collection', 'type']:
            if request.args.get(filter):
                filters[filter] = request.args.get(filter)
        res = get_filtered_feed(filters)

        if 'error' in res:
            return jsonify(res), 400
        data = {
            "feed": res,
        }
        return jsonify(data), 200

    @app.route('/api/latest', methods=['GET'])
    def get_latest():
        # Get the full feed and return the latest article
        feed = get_full_feed()
        # Gross
        first_key = list(feed.keys())[0]
        latest_article = {
            k: v for k, v in feed[first_key].items()
        }
        content_type, filename = latest_article['url'].split('/', 1)
        filename = filename + '.md'
        blob = get_blob(content_type, filename)
        data = parse_from_blob(blob)
        return jsonify(data), 200

    @app.route('/api/random', methods=['GET'])
    def get_random():
        # TODO: Farm this out to a helper function so we can use it in the website too
        # Get the full feed and return a random article
        feed = get_full_feed()
        random_article = random.choice(list(feed.values()))
        # Format the article
        formatted_random_article = {
            k: v for k, v in random_article.items()
        }
        # Set the date to the key
        formatted_random_article["date"] = list(random_article.keys())[0]
        content_type, filename = formatted_random_article['url'].split('/', 1)
        filename = filename + '.md'
        blob = get_blob(content_type, filename)

        data = parse_from_blob(blob)

        return jsonify(data), 200

    @app.route('/api/article/<path:url>', methods=['GET'])
    def get_article(url):
        if url.count('/') != 1:
            return jsonify({"error": "Invalid article URL - should be of form type/filename"}), 400
        content_type, filename = url.split('/', 1)
        filename = filename + '.md'
        try:
            blob = get_blob(content_type, filename)
        except:
            # We can abort with a 404 here
            return jsonify({"error": "Article not found"}), 404

        data = parse_from_blob(blob)
        return jsonify(data), 200

    @app.route('/api/recommendations', methods=['GET'])
    def return_all_recommendations():
        recommendations = get_all_recommendations()
        return jsonify(recommendations), 200

    @app.route("/api/recommendations/<path:url>", methods=['GET'])
    def get_recommendations(url):
        if not url.endswith('.md'):
            url = url + '.md'

        recommendations = get_ranked_recommendations(url)
        if 'error' in recommendations:
            return jsonify(recommendations), 400

        data = {
            "article": url,
            "recommendations": recommendations
        }
        return jsonify(data), 200

    @app.route("/api/static-pages")
    def get_pages():
        pages = get_static_pages()
        # Trim the md extension
        pages = [page.rstrip('.md') for page in pages]
        return jsonify(pages), 200

    @app.route("/api/static-pages/<path:url>")
    def get_page(url):
        pages = get_static_pages()
        pages = [page.rstrip('.md') for page in pages]
        if url not in pages:
            return jsonify({"error": "Page not found"}), 404
        # TODO: Make this a helper function so we can use it in the website too
        # Otherwise get the page
        blob = get_blob('', url + '.md')
        data = parse_from_blob(blob)

        # No metadata
        data.pop('metadata')

        data = {
            "page": url,
            "markdown": data['markdown']
        }
        return jsonify(data), 200

    @app.route('/api/categories', methods=['GET'])
    def get_categories():
        categories = DB.collection('collections')
        # All the doc ids are the categories
        categories_data = defaultdict(int)
        for doc in categories.stream():
            categories_data[doc.id] = len(doc.to_dict()['content'])
        categories = [
            {"category": k, "count": v} for k, v in categories_data.items()
        ]
        return jsonify(categories), 200

    @app.route('/api/tags', methods=['GET'])
    def get_tags():
        # Okay this is stupid but we have to get the full feed to get all the tags
        # Maybe I can use a {tag, frequency} setup to make it more worthwhile
        feed = get_full_feed()
        tag_data = defaultdict(int)
        for v in feed.values():
            for tag in clean_tags(v['tags']):
                tag_data[tag] += 1

        tag_data = [
            {"tag": k, "frequency": v} for k, v in tag_data.items()
        ]
        return jsonify(tag_data), 200

    @app.route('/api/authors', methods=['GET'])
    def get_authors():
        # This is from the feed again (I know, I know I wish I was using SQL too)
        feed = get_full_feed()
        author_data = defaultdict(int)
        for v in feed.values():
            author_data[v['author']] += 1

        author_data = [
            {"author": k, "frequency": v} for k, v in author_data.items()
        ]
        return jsonify(author_data), 200
