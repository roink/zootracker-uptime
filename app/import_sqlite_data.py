import argparse
import uuid
from typing import Dict

from sqlalchemy import MetaData, Table, create_engine, select, func, bindparam, text
from sqlalchemy.orm import Session

from .database import SessionLocal, Base
from . import models
from .utils.iucn import normalize_status


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
    """Insert animals and build id mapping.

    Existing animals are updated with new metadata when fields are missing.
    """

    existing = {
        row.art: row.id
        for row in dst.execute(select(models.Animal.id, models.Animal.art)).mappings()
        if row.art is not None
    }
    rows = list(src.execute(select(animal_table)).mappings())
    animals = []
    id_map: Dict[int, uuid.UUID] = {}
    for row in rows:
        art = row.get("art")
        desc_en = row.get("description_en") or row.get("english_summary")
        desc_de = row.get("description_de") or row.get("german_summary")
        status = normalize_status(row.get("iucn_conservation_status"))
        taxon_rank = row.get("taxon_rank")
        if art in existing:
            aid = existing[art]
            animal = dst.get(models.Animal, aid)
            changed = False

            def assign_if_missing(attr: str, value: str | None) -> None:
                nonlocal changed
                if value and getattr(animal, attr) in (None, ""):
                    setattr(animal, attr, value)
                    changed = True

            assign_if_missing("description_en", desc_en)
            assign_if_missing("description_de", desc_de)
            assign_if_missing("conservation_state", status)
            assign_if_missing("taxon_rank", taxon_rank)
            if changed:
                dst.add(animal)
            id_map[row["animal_id"]] = aid
            continue
        common_name = row.get("english_label") or row.get("german_label") or art
        animal = models.Animal(
            id=uuid.uuid4(),
            common_name=common_name,
            scientific_name=row.get("latin_name"),
            name_en=row.get("english_label"),
            name_de=row.get("german_label"),
            art=art,
            english_label=row.get("english_label"),
            german_label=row.get("german_label"),
            latin_name=row.get("latin_name"),
            klasse=row.get("klasse"),
            ordnung=row.get("ordnung"),
            familie=row.get("familie"),
            conservation_state=status,
            description_en=desc_en,
            description_de=desc_de,
            taxon_rank=taxon_rank,
            category_id=cat_map.get(row.get("klasse")),
        )
        animals.append(animal)
        id_map[row["animal_id"]] = animal.id
    if animals:
        dst.bulk_save_objects(animals)
    dst.commit()
    return id_map


def _import_zoos(src: Session, dst: Session, zoo_table: Table) -> Dict[int, uuid.UUID]:
    """Insert zoos from merged `zoo` table and return id mapping."""
    mapping: Dict[int, uuid.UUID] = {}
    rows = src.execute(select(zoo_table)).mappings()
    for row in rows:
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
            official_website=row.get("official_website"),
            wikipedia_en=row.get("wikipedia_en"),
            wikipedia_de=row.get("wikipedia_de"),
            description_en=row.get("description_en"),
            description_de=row.get("description_de"),
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
        )
        # Optional: set wikidata_id if our ORM model and source table have it
        if hasattr(models.Zoo, "wikidata_id") and "wikidata_id" in zoo_table.c:
            setattr(zoo, "wikidata_id", row.get("wikidata_id"))
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


def _ensure_columns(dst: Session) -> None:
    """Create new animal columns if they do not already exist."""
    dialect = dst.get_bind().dialect.name
    if dialect == "sqlite":
        cols = {row["name"] for row in dst.execute(text("PRAGMA table_info(animals)")).mappings()}
        if "description_de" not in cols:
            dst.execute(text("ALTER TABLE animals ADD COLUMN description_de TEXT"))
        if "description_en" not in cols:
            dst.execute(text("ALTER TABLE animals ADD COLUMN description_en TEXT"))
        if "conservation_state" not in cols:
            dst.execute(text("ALTER TABLE animals ADD COLUMN conservation_state TEXT"))
        if "taxon_rank" not in cols:
            dst.execute(text("ALTER TABLE animals ADD COLUMN taxon_rank TEXT"))
    else:
        dst.execute(text("ALTER TABLE animals ADD COLUMN IF NOT EXISTS description_de TEXT"))
        dst.execute(text("ALTER TABLE animals ADD COLUMN IF NOT EXISTS description_en TEXT"))
        dst.execute(text("ALTER TABLE animals ADD COLUMN IF NOT EXISTS conservation_state TEXT"))
        dst.execute(text("ALTER TABLE animals ADD COLUMN IF NOT EXISTS taxon_rank TEXT"))
    dst.commit()


def main(source: str) -> None:
    """Import data from a SQLite database file into the application's database."""
    source_url = f"sqlite:///{source}"
    src_engine = create_engine(source_url, future=True)
    src = Session(src_engine)
    dst = SessionLocal()
    try:
        Base.metadata.create_all(bind=dst.get_bind())
        _ensure_columns(dst)
        metadata = MetaData()
        animal_table = Table("animal", metadata, autoload_with=src_engine)
        zoo_table = Table("zoo", metadata, autoload_with=src_engine)
        link_table = Table("zoo_animal", metadata, autoload_with=src_engine)

        cat_map = _stage_categories(src, dst, animal_table)
        animal_map = _import_animals(src, dst, animal_table, cat_map)
        zoo_map = _import_zoos(src, dst, zoo_table)
        _import_links(src, dst, link_table, zoo_map, animal_map)
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import data from a SQLite dump")
    parser.add_argument("source", help="Path to source SQLite database")
    args = parser.parse_args()
    main(args.source)
