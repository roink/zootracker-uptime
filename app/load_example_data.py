"""Load example CSV data into the database."""

import csv
import sys
import uuid
from datetime import datetime, date
from pathlib import Path

from sqlalchemy.orm import Session

from .database import SessionLocal
from . import models
from .main import hash_password


def _uuid(val: str) -> uuid.UUID:
    return uuid.UUID(val)


def load_categories(db: Session, path: Path):
    with open(path / "categories.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(models.Category(id=_uuid(row["id"]), name=row["name"]))
    db.commit()


def load_animals(db: Session, path: Path):
    with open(path / "animals.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.Animal(
                    id=_uuid(row["id"]),
                    common_name=row["common_name"],
                    category_id=_uuid(row["category_id"]),
                )
            )
    db.commit()


def load_zoos(db: Session, path: Path):
    with open(path / "zoos.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.Zoo(
                    id=_uuid(row["id"]),
                    name=row["name"],
                    address=row["address"],
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    description=row["description"],
                )
            )
    db.commit()


def load_users(db: Session, path: Path):
    with open(path / "users.csv", newline="") as f:
        for row in csv.DictReader(f):
            salt, hashed = hash_password(row["password"])
            db.add(
                models.User(
                    id=_uuid(row["id"]),
                    name=row["name"],
                    email=row["email"],
                    password_salt=salt,
                    password_hash=hashed,
                )
            )
    db.commit()


def load_achievements(db: Session, path: Path):
    with open(path / "achievements.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.Achievement(
                    id=_uuid(row["id"]),
                    name=row["name"],
                    description=row.get("description"),
                )
            )
    db.commit()


def load_user_achievements(db: Session, path: Path):
    with open(path / "user_achievements.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.UserAchievement(
                    id=_uuid(row["id"]),
                    user_id=_uuid(row["user_id"]),
                    achievement_id=_uuid(row["achievement_id"]),
                )
            )
    db.commit()


def load_zoo_animals(db: Session, path: Path):
    with open(path / "zoo_animals.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.ZooAnimal(
                    zoo_id=_uuid(row["zoo_id"]),
                    animal_id=_uuid(row["animal_id"]),
                )
            )
    db.commit()


def load_zoo_visits(db: Session, path: Path):
    with open(path / "zoo_visits.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.ZooVisit(
                    id=_uuid(row["id"]),
                    user_id=_uuid(row["user_id"]),
                    zoo_id=_uuid(row["zoo_id"]),
                    visit_date=date.fromisoformat(row["visit_date"]),
                )
            )
    db.commit()


def load_animal_sightings(db: Session, path: Path):
    with open(path / "animal_sightings.csv", newline="") as f:
        for row in csv.DictReader(f):
            db.add(
                models.AnimalSighting(
                    id=_uuid(row["id"]),
                    user_id=_uuid(row["user_id"]),
                    zoo_id=_uuid(row["zoo_id"]),
                    animal_id=_uuid(row["animal_id"]),
                    sighting_datetime=datetime.fromisoformat(row["sighting_datetime"]),
                )
            )
    db.commit()


LOAD_ORDER = [
    load_categories,
    load_animals,
    load_zoos,
    load_users,
    load_achievements,
    load_user_achievements,
    load_zoo_animals,
    load_zoo_visits,
    load_animal_sightings,
]


def main(data_path: str = "example_data"):
    path = Path(data_path)
    db = SessionLocal()
    try:
        for func in LOAD_ORDER:
            func(db, path)
    finally:
        db.close()


if __name__ == "__main__":
    data_path = sys.argv[1] if len(sys.argv) > 1 else "example_data"
    main(data_path)
