import uuid
from datetime import date, datetime
from .conftest import client, register_and_login, SessionLocal
from app import models

def test_post_visit_and_retrieve(data):
    """Create a visit and verify it can be retrieved."""
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(zoo_id)

def test_visit_requires_auth(data):
    _, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(f"/users/{user_id}/visits", json=visit)
    assert resp.status_code == 401

def test_create_visit_requires_json(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        "/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415

def test_create_visit_accepts_charset(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        "/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200

def test_create_visit_for_user_requires_json(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415

def test_create_visit_for_user_accepts_charset(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200

def test_visit_wrong_user(data):
    token1, user1 = register_and_login()
    _, user2 = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user2}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 403

def test_multiple_visits(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit1 = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit1,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    tomorrow = date.fromordinal(date.today().toordinal() + 1)
    visit2 = {"zoo_id": str(zoo_id), "visit_date": str(tomorrow)}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit2,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 2

def test_get_visits_requires_auth():
    resp = client.get("/visits")
    assert resp.status_code == 401

def test_get_visits_empty(data):
    token, _ = register_and_login()
    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []

def test_visits_are_user_specific(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user1}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 1

def test_visit_missing_zoo_id_fails(data):
    token, user_id = register_and_login()
    visit = {"visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

def test_visit_missing_date_fails(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id)}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

def test_visit_has_user_id_in_db(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    visit_id = resp.json()["id"]
    db = SessionLocal()
    stored = db.get(models.ZooVisit, uuid.UUID(visit_id))
    db.close()
    assert stored is not None
    assert stored.user_id == uuid.UUID(user_id)

def test_visit_extra_field_rejected(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {
        "zoo_id": str(zoo_id),
        "visit_date": str(date.today()),
        "unexpected": "boom",
    }
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

def test_visit_notes_too_long(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {
        "zoo_id": str(zoo_id),
        "visit_date": str(date.today()),
        "notes": "n" * 1001,
    }
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

def test_create_visit_invalid_zoo(data):
    token, _ = register_and_login()
    visit = {"zoo_id": str(uuid.uuid4()), "visit_date": str(date.today())}
    resp = client.post(
        "/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

def test_create_visit_for_user_invalid_zoo(data):
    token, user_id = register_and_login()
    visit = {"zoo_id": str(uuid.uuid4()), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404

def test_delete_visit_success(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    visit_id = resp.json()["id"]

    resp = client.delete(
        f"/visits/{visit_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204
    db = SessionLocal()
    deleted = db.get(models.ZooVisit, uuid.UUID(visit_id))
    db.close()
    assert deleted is None

def test_delete_visit_unauthorized(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user1}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    visit_id = resp.json()["id"]

    resp = client.delete(
        f"/visits/{visit_id}", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp.status_code == 403

def test_patch_visit_success(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    visit_id = resp.json()["id"]

    tomorrow = date.fromordinal(date.today().toordinal() + 1)
    resp = client.patch(
        f"/visits/{visit_id}",
        json={"visit_date": str(tomorrow), "notes": "updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["visit_date"] == str(tomorrow)
    assert body["notes"] == "updated"

def test_patch_visit_forbidden(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user1}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    visit_id = resp.json()["id"]

    resp = client.patch(
        f"/visits/{visit_id}",
        json={"notes": "hacked"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
