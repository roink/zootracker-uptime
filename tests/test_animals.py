import uuid
from datetime import date, datetime
from .conftest import client, register_and_login, SessionLocal
from app import models

def test_get_animal_detail_success(data):
    resp = client.get(f"/animals/{data['animal'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["animal"].id)
    assert body["zoos"][0]["id"] == str(data["zoo"].id)

def test_get_animal_detail_not_found():
    resp = client.get(f"/animals/{uuid.uuid4()}")
    assert resp.status_code == 404
