"""Load example CSV data into the database."""

import csv
import sys
import uuid
from datetime import datetime, date
from pathlib import Path
from functools import partial

from sqlalchemy.orm import Session

from .database import SessionLocal
from . import models
from .auth import hash_password
from .create_tables import create_tables


def _uuid(val: str) -> uuid.UUID:
    return uuid.UUID(val)


def load_csv(
    db: Session,
    path: Path,
    file_name: str,
    model_cls,
    field_map: dict,
    preprocess=None,
):
    """Generic CSV loader that maps fields and inserts model instances."""
    with open(path / file_name, newline="") as f:
        objs = []
        for row in csv.DictReader(f):
            data = {}
            for model_field, spec in field_map.items():
                if isinstance(spec, tuple):
                    csv_field, conv = spec
                else:
                    csv_field, conv = model_field, spec
                value = row[csv_field]
                data[model_field] = conv(value) if conv else value
            if preprocess:
                data = preprocess(data)
            objs.append(model_cls(**data))
        db.add_all(objs)
    db.commit()


load_categories = partial(
    load_csv,
    file_name="categories.csv",
    model_cls=models.Category,
    field_map={"id": ("id", _uuid), "name": ("name", None)},
)

load_animals = partial(
    load_csv,
    file_name="animals.csv",
    model_cls=models.Animal,
    field_map={
        "id": ("id", _uuid),
        "common_name": ("common_name", None),
        "category_id": ("category_id", _uuid),
    },
)

load_zoos = partial(
    load_csv,
    file_name="zoos.csv",
    model_cls=models.Zoo,
    field_map={
        "id": ("id", _uuid),
        "name": ("name", None),
        "address": ("address", None),
        "latitude": ("latitude", float),
        "longitude": ("longitude", float),
        "description": ("description", None),
    },
)

load_users = partial(
    load_csv,
    file_name="users.csv",
    model_cls=models.User,
    field_map={
        "id": ("id", _uuid),
        "name": ("name", None),
        "email": ("email", None),
        "password_hash": ("password", hash_password),
    },
)

load_achievements = partial(
    load_csv,
    file_name="achievements.csv",
    model_cls=models.Achievement,
    field_map={
        "id": ("id", _uuid),
        "name": ("name", None),
        "description": ("description", None),
    },
)

load_user_achievements = partial(
    load_csv,
    file_name="user_achievements.csv",
    model_cls=models.UserAchievement,
    field_map={
        "id": ("id", _uuid),
        "user_id": ("user_id", _uuid),
        "achievement_id": ("achievement_id", _uuid),
    },
)

load_zoo_animals = partial(
    load_csv,
    file_name="zoo_animals.csv",
    model_cls=models.ZooAnimal,
    field_map={
        "zoo_id": ("zoo_id", _uuid),
        "animal_id": ("animal_id", _uuid),
    },
)

load_zoo_visits = partial(
    load_csv,
    file_name="zoo_visits.csv",
    model_cls=models.ZooVisit,
    field_map={
        "id": ("id", _uuid),
        "user_id": ("user_id", _uuid),
        "zoo_id": ("zoo_id", _uuid),
        "visit_date": ("visit_date", lambda v: date.fromisoformat(v)),
    },
)

load_animal_sightings = partial(
    load_csv,
    file_name="animal_sightings.csv",
    model_cls=models.AnimalSighting,
    field_map={
        "id": ("id", _uuid),
        "user_id": ("user_id", _uuid),
        "zoo_id": ("zoo_id", _uuid),
        "animal_id": ("animal_id", _uuid),
        "sighting_datetime": (
            "sighting_datetime",
            lambda v: datetime.fromisoformat(v),
        ),
    },
)

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
    create_tables()
    db = SessionLocal()
    try:
        for loader in LOAD_ORDER:
            loader(db, path)
    finally:
        db.close()


if __name__ == "__main__":
    data_path = sys.argv[1] if len(sys.argv) > 1 else "example_data"
    main(data_path)
