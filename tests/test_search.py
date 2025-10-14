from .conftest import client


def test_animal_search_returns_results(data):
    resp = client.get('/animals', params={'q': 'Lion', 'limit': 5})
    assert resp.status_code == 200
    animals = resp.json()
    assert any(a['id'] == str(data['animal'].id) for a in animals)
    lion = next((a for a in animals if a['id'] == str(data['animal'].id)), None)
    assert lion is not None
    assert lion['default_image_url'] == data['animal'].default_image_url


def test_animal_search_limit(data):
    resp = client.get('/animals', params={'limit': 1})
    assert resp.status_code == 200
    animals = resp.json()
    assert len(animals) == 1


def test_zoo_search_returns_results(data):
    resp = client.get('/zoos', params={'q': data['zoo'].name, 'limit': 5})
    assert resp.status_code == 200
    body = resp.json()
    items = body['items']
    assert any(z['id'] == str(data['zoo'].id) for z in items)


def test_zoo_search_by_city(data):
    resp = client.get('/zoos', params={'q': data['zoo'].city})
    assert resp.status_code == 200
    items = resp.json()['items']
    assert any(z.get('city') == data['zoo'].city for z in items)


def test_zoo_search_limit(data):
    resp = client.get('/zoos', params={'limit': 1})
    assert resp.status_code == 200
    body = resp.json()
    items = body['items']
    assert len(items) == 1
    assert body['limit'] == 1
