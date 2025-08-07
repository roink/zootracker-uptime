from app.database import SessionLocal
from app import models


def test_zoo_animal_counts_update(data):
    """Zoo and animal counters should update when links change."""
    db = SessionLocal()
    zoo = db.get(models.Zoo, data["zoo"].id)
    animal = db.get(models.Animal, data["animal"].id)

    # Seed data links one animal to one zoo
    assert zoo.animal_count == 1
    assert animal.zoo_count == 1

    tiger = db.get(models.Animal, data["tiger"].id)
    link = models.ZooAnimal(zoo_id=zoo.id, animal_id=tiger.id)
    db.add(link)
    db.commit()
    db.refresh(zoo)
    db.refresh(tiger)
    assert zoo.animal_count == 2
    assert tiger.zoo_count == 1

    db.delete(link)
    db.commit()
    db.refresh(zoo)
    db.refresh(tiger)
    assert zoo.animal_count == 1
    assert tiger.zoo_count == 0
    db.close()

