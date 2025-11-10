


async def test_animal_search_returns_results(client, data):
    resp = await client.get('/animals', params={'q': 'Lion', 'limit': 5})
    assert resp.status_code == 200
    body = resp.json()
    animals = body['items']
    assert any(a['id'] == str(data['animal'].id) for a in animals)
    lion = next((a for a in animals if a['id'] == str(data['animal'].id)), None)
    assert lion is not None
    assert lion['default_image_url'] == data['animal'].default_image_url


async def test_animal_search_limit(client, data):
    resp = await client.get('/animals', params={'limit': 1})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body['items']) == 1


async def test_zoo_search_returns_results(client, data):
    resp = await client.get('/zoos', params={'q': data['zoo'].name, 'limit': 5})
    assert resp.status_code == 200
    body = resp.json()
    items = body['items']
    assert any(z['id'] == str(data['zoo'].id) for z in items)


async def test_zoo_search_by_city(client, data):
    resp = await client.get('/zoos', params={'q': data['zoo'].city})
    assert resp.status_code == 200
    items = resp.json()['items']
    assert any(z.get('city') == data['zoo'].city for z in items)


async def test_zoo_search_limit(client, data):
    resp = await client.get('/zoos', params={'limit': 1})
    assert resp.status_code == 200
    body = resp.json()
    items = body['items']
    assert len(items) == 1
    assert body['limit'] == 1
