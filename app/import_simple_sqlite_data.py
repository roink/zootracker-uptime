import argparse
import logging
import uuid
from typing import Dict, Tuple

from sqlalchemy import MetaData, Table, create_engine, select, func, bindparam, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .database import SessionLocal, Base
from . import models
from .utils.iucn import normalize_status
from .import_utils import _ensure_animal_columns


logger = logging.getLogger(__name__)


def _stage_categories(src: Session, dst: Session, animal_table: Table) -> Dict[int | None, uuid.UUID]:
    """Ensure a :class:`Category` exists for each distinct ``klasse`` value."""

    klasses = [row["klasse"] for row in src.execute(select(animal_table.c.klasse).distinct()).mappings()]
    existing = {
        row.name: row.id
        for row in dst.execute(select(models.Category.id, models.Category.name)).mappings()
    }
    mapping: Dict[int | None, uuid.UUID] = {}
    to_add = []
    for k in klasses:
        name = f"Klasse {k}" if k is not None else "Uncategorized"
        if name in existing:
            mapping[k] = existing[name]
            continue
        cid = uuid.uuid4()
        to_add.append(models.Category(id=cid, name=name))
        existing[name] = cid
        mapping[k] = cid
    if to_add:
        dst.bulk_save_objects(to_add)
    return mapping


def _import_animals(
    src: Session,
    dst: Session,
    animal_table: Table,
    cat_map: Dict[int | None, uuid.UUID],
    overwrite: bool = False,
) -> Dict[str, uuid.UUID]:
    """Insert animals and build id mapping keyed by ``art``.

    Existing animals are updated with new metadata when fields are missing.
    """

    existing = {
        row.art: row.id
        for row in dst.execute(select(models.Animal.id, models.Animal.art)).mappings()
        if row.art is not None
    }
    rows = list(src.execute(select(animal_table)).mappings())
    animals = []
    id_map: Dict[str, uuid.UUID] = {}
    for row in rows:
        art = row.get("art")
        # only import explicit description_de; ignore legacy zootierliste_description
        desc_de = row.get("description_de")
        if desc_de:
            desc_de = desc_de.strip()
        desc_en = row.get("description_en")
        if desc_en:
            desc_en = desc_en.strip()
        status = normalize_status(row.get("iucn_conservation_status"))
        taxon_rank = row.get("taxon_rank")
        if taxon_rank:
            taxon_rank = taxon_rank.strip()
        if art in existing:
            aid = existing[art]
            animal = dst.get(models.Animal, aid)
            changed = False

            def assign(attr: str, value: str | None) -> None:
                nonlocal changed
                current = getattr(animal, attr)
                if overwrite:
                    if current != value:
                        setattr(animal, attr, value)
                        changed = True
                else:
                    if current in (None, "") and value:
                        setattr(animal, attr, value)
                        changed = True

            assign("description_de", desc_de)
            assign("description_en", desc_en)
            assign("conservation_state", status)
            assign("taxon_rank", taxon_rank)
            if changed:
                dst.add(animal)
            id_map[art] = aid
            continue
        if not row.get("latin_name") or not row.get("name_de"):
            logger.warning("Animal %s missing latin or German name", art)
        common_name = row.get("name_de") or row.get("latin_name") or art
        aid = uuid.uuid4()
        animals.append(
            models.Animal(
                id=aid,
                common_name=common_name,
                scientific_name=row.get("latin_name"),
                name_de=row.get("name_de"),
                name_en=row.get("name_en"),
                latin_name=row.get("latin_name"),
                art=art,
                klasse=row.get("klasse"),
                ordnung=row.get("ordnung"),
                familie=row.get("familie"),
                description_en=desc_en,
                description_de=desc_de,
                conservation_state=status,
                taxon_rank=taxon_rank,
                category_id=cat_map.get(row.get("klasse")),
            )
        )
        id_map[art] = aid
    if animals:
        dst.bulk_save_objects(animals)
    return id_map


def _import_zoos(src: Session, dst: Session, zoo_table: Table) -> Dict[int, uuid.UUID]:
    """Insert zoos and build id mapping."""

    existing = {
        (row.name, row.city, row.country): row.id
        for row in dst.execute(
            select(models.Zoo.id, models.Zoo.name, models.Zoo.city, models.Zoo.country)
        ).mappings()
    }
    rows = list(src.execute(select(zoo_table)).mappings())
    zoos = []
    mapping: Dict[int, uuid.UUID] = {}
    for row in rows:
        key: Tuple[str, str, str] = (
            row.get("name"),
            row.get("city"),
            row.get("country"),
        )
        if key in existing:
            mapping[row["zoo_id"]] = existing[key]
            continue
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat is not None and not (-90 <= lat <= 90):
            logger.warning("Zoo %s has invalid latitude %s", row.get("name"), lat)
            lat = None
        if lon is not None and not (-180 <= lon <= 180):
            logger.warning("Zoo %s has invalid longitude %s", row.get("name"), lon)
            lon = None
        zid = uuid.uuid4()
        zoos.append(
            models.Zoo(
                id=zid,
                name=row.get("name"),
                country=row.get("country"),
                city=row.get("city"),
                latitude=lat,
                longitude=lon,
            )
        )
        mapping[row["zoo_id"]] = zid
        existing[key] = zid
    if zoos:
        dst.bulk_save_objects(zoos)
    return mapping


def _import_links(
    src: Session,
    dst: Session,
    link_table: Table,
    zoo_map: Dict[int, uuid.UUID],
    animal_map: Dict[str, uuid.UUID],
) -> None:
    rows = src.execute(select(link_table)).mappings()
    # use dialect-appropriate "ignore duplicates" syntax
    if dst.get_bind().dialect.name == "postgresql":
        stmt = pg_insert(models.ZooAnimal.__table__).on_conflict_do_nothing()
    else:
        stmt = insert(models.ZooAnimal.__table__).prefix_with("OR IGNORE")
    batch: list[dict] = []
    batch_size = 1000
    processed = 0
    for row in rows:
        z_id = zoo_map.get(row["zoo_id"])
        a_id = animal_map.get(row["art"])
        if z_id and a_id:
            batch.append({"zoo_id": z_id, "animal_id": a_id})
            if len(batch) >= batch_size:
                try:
                    dst.execute(stmt, batch)
                except Exception as exc:  # pragma: no cover - defensive
                    err = getattr(exc, "orig", exc)
                    logger.error(
                        "Failed inserting link batch %d-%d: %s",
                        processed,
                        processed + len(batch),
                        err,
                    )
                    raise
                processed += len(batch)
                batch.clear()
    if batch:
        try:
            dst.execute(stmt, batch)
        except Exception as exc:  # pragma: no cover - defensive
            err = getattr(exc, "orig", exc)
            logger.error(
                "Failed inserting link batch %d-%d: %s",
                processed,
                processed + len(batch),
                err,
            )
            raise
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


def main(source: str, dry_run: bool = False, overwrite: bool = False) -> None:
    """Import data from a SQLite database file into the application's database."""

    logging.basicConfig(level=logging.INFO)
    source_url = f"sqlite:///{source}"
    src_engine = create_engine(source_url, future=True)
    src = Session(src_engine)
    dst = SessionLocal()
    try:
        Base.metadata.create_all(bind=dst.get_bind())
        _ensure_animal_columns(dst)
        metadata = MetaData()
        animal_table = Table("animal", metadata, autoload_with=src_engine)
        zoo_table = Table("zoo", metadata, autoload_with=src_engine)
        link_table = Table("zoo_animal", metadata, autoload_with=src_engine)

        with dst.begin() as trans:
            cat_map = _stage_categories(src, dst, animal_table)
            animal_map = _import_animals(
                src, dst, animal_table, cat_map, overwrite=overwrite
            )
            zoo_map = _import_zoos(src, dst, zoo_table)
            _import_links(src, dst, link_table, zoo_map, animal_map)
            if dry_run:
                logger.info("Dry run requested; rolling back changes")
                trans.rollback()
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import data from a SQLite dump with minimal schema"
    )
    parser.add_argument("source", help="Path to source SQLite database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and log counts without writing",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing field values with those from the source",
    )
    args = parser.parse_args()
    main(args.source, dry_run=args.dry_run, overwrite=args.overwrite)
