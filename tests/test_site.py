from sqlalchemy import func

from .conftest import client
from app.database import SessionLocal
from app import models


def test_site_summary_counts(data):
    """Landing summary should expose global counts."""
    db = SessionLocal()
    expected_species = db.query(models.Animal).count()
    expected_zoos = db.query(models.Zoo).count()
    expected_countries = (
        db.query(func.count(func.distinct(models.Zoo.country_id)))
        .filter(models.Zoo.country_id.isnot(None))
        .scalar()
    )
    expected_sightings = db.query(models.AnimalSighting).count()
    db.close()
    resp = client.get("/site/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["species"] == expected_species
    assert body["zoos"] == expected_zoos
    assert body["countries"] == expected_countries
    assert body["sightings"] == expected_sightings


def test_popular_animals_sorted_by_zoo_count(data):
    """Popular animals should be ordered by the number of zoos keeping them."""
    # Link another zoo to ensure counts differ
    db = SessionLocal()
    tiger = db.get(models.Animal, data["tiger"].id)
    far_zoo = db.get(models.Zoo, data["far_zoo"].id)
    db.add(models.ZooAnimal(zoo_id=far_zoo.id, animal_id=tiger.id))
    db.commit()
    db.refresh(tiger)
    db.close()

    resp = client.get("/site/popular-animals", params={"limit": 5})
    assert resp.status_code == 200
    items = resp.json()
    # Seeded data contains three animals, lion should be first with zoo_count >= tiger
    assert len(items) == 3
    assert items[0]["slug"] == "lion"
    assert items[0]["zoo_count"] >= items[1]["zoo_count"]


def test_popular_animals_limit_validation():
    resp = client.get("/site/popular-animals", params={"limit": 25})
    assert resp.status_code == 400
    body = resp.json()
    assert "limit" in body["detail"].lower()
