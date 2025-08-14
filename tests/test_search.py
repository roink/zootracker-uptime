from .conftest import client


def test_combined_search(data):
    resp = client.get('/search', params={'q': 'Zoo', 'limit': 5})
    assert resp.status_code == 200
    body = resp.json()
    assert 'zoos' in body and 'animals' in body
    assert any(z['id'] == str(data['zoo'].id) for z in body['zoos'])


def test_search_limit(data):
    resp = client.get('/search', params={'limit': 1})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body['zoos']) == 1
    assert len(body['animals']) == 1


def test_search_includes_city(data):
    """Zoo items should include their city to display \"City: Name\"."""
    resp = client.get('/search', params={'q': 'Central'})
    assert resp.status_code == 200
    body = resp.json()
    assert any(z.get('city') == data['zoo'].city for z in body['zoos'])
