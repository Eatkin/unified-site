import pytest
from app import app

from unittest.mock import patch

# Create a test client
@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# Test for commands endpoint
def test_get_commands(client):
    response = client.get('/api/commands')
    assert response.status_code == 200
    data = response.get_json()
    assert 'Hello' in data
    assert data['Hello'] == 'Hello there!'

# Test for the feed with filters
def test_get_feed_with_filters(client):
    response = client.get('/api/feed?tags=python,flask&collection=eds_blog')
    assert response.status_code == 200
    data = response.get_json()
    assert 'feed' in data
    assert len(data['feed']) > 0

# Test for the latest article
def test_get_latest(client):
    response = client.get('/api/latest')
    assert response.status_code == 200
    data = response.get_json()
    assert 'metadata' in data
    assert 'markdown' in data

# Test for random article
def test_get_random(client):
    response = client.get('/api/random')
    assert response.status_code == 200
    data = response.get_json()
    assert 'metadata' in data
    assert 'markdown' in data

# Test for article endpoint (valid and invalid)
def test_get_article_valid(client):
    response = client.get('/api/article/blog/hello_world')
    assert response.status_code == 200
    data = response.get_json()
    assert 'metadata' in data
    assert 'markdown' in data

def test_get_article_invalid(client):
    response = client.get('/api/article/type/invalid-url')
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data

# Test categories endpoint
def test_get_categories(client):
    response = client.get('/api/categories')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)

# Test tags endpoint
def test_get_tags(client):
    response = client.get('/api/tags')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)

# Test authors endpoint
def test_get_authors(client):
    response = client.get('/api/authors')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
