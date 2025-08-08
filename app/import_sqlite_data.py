import argparse
import uuid
from typing import Dict

from sqlalchemy import MetaData, Table, create_engine, select, func, bindparam
from sqlalchemy.orm import Session

from .database import SessionLocal, Base
from . import models


def _stage_categories(src: Session, dst: Session, animal_table: Table) -> Dict[int, uuid.UUID]:
    """Ensure a Category exists for each distinct ``klasse`` value."""
    klasses = [row["klasse"] for row in src.execute(select(animal_table.c.klasse).distinct()).mappings() if row["klasse"] is not None]
    mapping: Dict[int, uuid.UUID] = {}
    for k in klasses:
        name = f"Klasse {k}"
        existing = dst.execute(select(models.Category).where(models.Category.name == name)).scalar_one_or_none()
        if not existing:
            cat = models.Category(id=uuid.uuid4(), name=name)
            dst.add(cat)
            dst.flush()
            mapping[k] = cat.id
        else:
            mapping[k] = existing.id
    dst.commit()
    return mapping


def _import_animals(src: Session, dst: Session, animal_table: Table, cat_map: Dict[int, uuid.UUID]) -> Dict[int, uuid.UUID]:
    """Insert animals and build id mapping."""
    id_map: Dict[int, uuid.UUID] = {}
    rows = src.execute(select(animal_table)).mappings()
    for row in rows:
        common_name = row.get("english_label") or row.get("german_label") or row.get("art")
        animal = models.Animal(
            id=uuid.uuid4(),
            common_name=common_name,
            scientific_name=row.get("latin_name"),
            name_en=row.get("english_label"),
            name_de=row.get("german_label"),
            art=row.get("art"),
            english_label=row.get("english_label"),
            german_label=row.get("german_label"),
            latin_name=row.get("latin_name"),
            klasse=row.get("klasse"),
            ordnung=row.get("ordnung"),
            familie=row.get("familie"),
            conservation_state=row.get("iucn_conservation_status"),
            description_en=row.get("english_summary"),
            description_de=row.get("german_summary"),
            category_id=cat_map.get(row.get("klasse")),
        )
        dst.add(animal)
        dst.flush()
        id_map[row["animal_id"]] = animal.id
    dst.commit()
    return id_map


def _import_zoos(src: Session, dst: Session, zoo_table: Table, desc_table: Table) -> Dict[int, uuid.UUID]:
    """Insert zoos and return id mapping."""
    descs = {row["zoo_id"]: row for row in src.execute(select(desc_table)).mappings()}
    mapping: Dict[int, uuid.UUID] = {}
    rows = src.execute(select(zoo_table)).mappings()
    for row in rows:
        desc = descs.get(row["zoo_id"], {})
        name = row.get("name") or row.get("label_en") or row.get("label_de")
        zoo = models.Zoo(
            id=uuid.uuid4(),
            name=name,
            default_label=row.get("default_label"),
            label_en=row.get("label_en"),
            label_de=row.get("label_de"),
            country=row.get("country"),
            city=row.get("city"),
            continent=row.get("continent"),
            official_website=desc.get("official_website"),
            wikipedia_en=desc.get("wikipedia_en") or row.get("wikipedia_en"),
            wikipedia_de=desc.get("wikipedia_de") or row.get("wikipedia_de"),
            description_en=desc.get("description_en"),
            description_de=desc.get("description_de"),
            latitude=desc.get("latitude"),
            longitude=desc.get("longitude"),
        )
        dst.add(zoo)
        dst.flush()
        mapping[row["zoo_id"]] = zoo.id
    dst.commit()
    return mapping


def _import_links(src: Session, dst: Session, link_table: Table, zoo_map: Dict[int, uuid.UUID], animal_map: Dict[int, uuid.UUID]) -> None:
    rows = src.execute(select(link_table)).mappings()
    for row in rows:
        z_id = zoo_map.get(row["zoo_id"])
        a_id = animal_map.get(row["animal_id"])
        if z_id and a_id:
            dst.add(models.ZooAnimal(zoo_id=z_id, animal_id=a_id))
    dst.commit()
    # recompute counters in bulk
    zoo_counts = dst.execute(
        select(models.ZooAnimal.zoo_id, func.count().label("cnt")).group_by(models.ZooAnimal.zoo_id)
    ).all()
    if zoo_counts:
        dst.execute(
            models.Zoo.__table__.update().where(models.Zoo.id == bindparam("z_id")),
            [{"z_id": z_id, "animal_count": cnt} for z_id, cnt in zoo_counts],
        )
    animal_counts = dst.execute(
        select(models.ZooAnimal.animal_id, func.count().label("cnt")).group_by(models.ZooAnimal.animal_id)
    ).all()
    if animal_counts:
        dst.execute(
            models.Animal.__table__.update().where(models.Animal.id == bindparam("a_id")),
            [{"a_id": a_id, "zoo_count": cnt} for a_id, cnt in animal_counts],
        )
    dst.commit()


def main(source: str) -> None:
    """Import data from a SQLite database file into the application's database."""
    source_url = f"sqlite:///{source}"
    src_engine = create_engine(source_url, future=True)
    src = Session(src_engine)
    dst = SessionLocal()
    try:
        Base.metadata.create_all(bind=dst.get_bind())
        metadata = MetaData()
        animal_table = Table("animal", metadata, autoload_with=src_engine)
        zoo_table = Table("zoo", metadata, autoload_with=src_engine)
        desc_table = Table("zoo_openAI_descriptions", metadata, autoload_with=src_engine)
        link_table = Table("zoo_animal", metadata, autoload_with=src_engine)

        cat_map = _stage_categories(src, dst, animal_table)
        animal_map = _import_animals(src, dst, animal_table, cat_map)
        zoo_map = _import_zoos(src, dst, zoo_table, desc_table)
        _import_links(src, dst, link_table, zoo_map, animal_map)
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import data from a SQLite dump")
    parser.add_argument("source", help="Path to source SQLite database")
    args = parser.parse_args()
    main(args.source)
