import argparse
import uuid
import re
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy import MetaData, Table, create_engine, select, func, bindparam, inspect
from sqlalchemy.orm import Session

from .database import SessionLocal, Base
from . import models
from .utils.iucn import normalize_status
from .import_utils import (
    _ensure_animal_columns,
    _ensure_image_columns,
    _clean_text,
    _parse_datetime,
)


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


def _import_animals(
    src: Session,
    dst: Session,
    animal_table: Table,
    cat_map: Dict[int, uuid.UUID],
    overwrite: bool = False,
) -> Dict[int, uuid.UUID]:
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
        if desc_en:
            desc_en = desc_en.strip()
        desc_de = row.get("description_de") or row.get("german_summary")
        if desc_de:
            desc_de = desc_de.strip()
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

            assign("description_en", desc_en)
            assign("description_de", desc_de)
            assign("conservation_state", status)
            assign("taxon_rank", taxon_rank)
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
            description_en=desc_en,
            description_de=desc_de,
            conservation_state=status,
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


def _import_images(
    src: Session,
    dst: Session,
    image_table: Table,
    variant_table: Table,
    animal_map: Dict[int, uuid.UUID],
    overwrite: bool = False,
) -> None:
    """Insert images and thumbnail variants."""

    img_rows = list(src.execute(select(image_table)).mappings())
    images: list[models.Image] = []
    mid_to_animal: Dict[str, uuid.UUID] = {}
    existing = {img.mid: img for img in dst.execute(select(models.Image)).scalars()}
    for row in img_rows:
        mid = row.get("mid")
        key = row.get("animal_art") or row.get("animal_id")
        aid = animal_map.get(key)
        if not aid:
            continue

        width = row.get("width")
        height = row.get("height")
        size_bytes = row.get("size_bytes")
        mime = row.get("mime")
        sha1 = row.get("sha1")
        original_url = row.get("original_url")
        source = row.get("source")
        if (
            width is None
            or width <= 0
            or height is None
            or height <= 0
            or size_bytes is None
            or size_bytes < 0
            or not mime
            or not mime.startswith("image/")
            or not sha1
            or not re.fullmatch(r"[0-9a-f]{40}", sha1)
            or not original_url
            or source not in {"WIKIDATA_P18", "WIKI_LEAD_DE", "WIKI_LEAD_EN"}
        ):
            continue

        uploaded_at = _parse_datetime(row.get("uploaded_at"))
        retrieved_at = _parse_datetime(row.get("retrieved_at")) or datetime.now(timezone.utc)
        attr_req = row.get("attribution_required")
        attr_bool = None
        if attr_req is not None:
            try:
                attr_bool = bool(int(attr_req))
            except (TypeError, ValueError):
                attr_bool = None

        data = {
            "mid": mid,
            "animal_id": aid,
            "commons_title": row.get("commons_title"),
            "commons_page_url": row.get("commons_page_url"),
            "original_url": original_url,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "sha1": sha1,
            "mime": mime,
            "uploaded_at": uploaded_at,
            "uploader": _clean_text(row.get("uploader")),
            "title": _clean_text(row.get("title")),
            "artist_raw": _clean_text(row.get("artist_raw")),
            "artist_plain": _clean_text(row.get("artist_plain")),
            "license": _clean_text(row.get("license")),
            "license_short": _clean_text(row.get("license_short")),
            "license_url": _clean_text(row.get("license_url")),
            "attribution_required": attr_bool,
            "usage_terms": _clean_text(row.get("usage_terms")),
            "credit_line": _clean_text(row.get("credit_line")),
            "source": source,
            "retrieved_at": retrieved_at,
        }

        if mid in existing:
            mid_to_animal[mid] = aid or existing[mid].animal_id
            if overwrite:
                for k, v in data.items():
                    setattr(existing[mid], k, v)
                dst.add(existing[mid])
            continue

        images.append(models.Image(**data))
        mid_to_animal[mid] = aid
    if images:
        dst.bulk_save_objects(images)

    var_rows = list(src.execute(select(variant_table)).mappings())
    variants: list[models.ImageVariant] = []
    best_variant: Dict[uuid.UUID, tuple[int, str]] = {}
    existing_vars = set(
        dst.execute(select(models.ImageVariant.mid, models.ImageVariant.width)).all()
    )
    for row in var_rows:
        key = (row.get("mid"), row.get("width"))
        if key in existing_vars:
            continue
        variants.append(
            models.ImageVariant(
                mid=row.get("mid"),
                width=row.get("width"),
                height=row.get("height"),
                thumb_url=row.get("thumb_url"),
            )
        )
        aid = mid_to_animal.get(row.get("mid"))
        if aid:
            width = row.get("width")
            url = row.get("thumb_url")
            current = best_variant.get(aid)
            if current is None or (
                current[0] != 640 and (width == 640 or width > current[0])
            ):
                best_variant[aid] = (width, url)
    if variants:
        dst.bulk_save_objects(variants)

    if best_variant:
        dst.execute(
            models.Animal.__table__
            .update()
            .where(
                models.Animal.id == bindparam("aid"),
                models.Animal.default_image_url.is_(None),
            ),
            [
                {"aid": aid, "default_image_url": url}
                for aid, (_, url) in best_variant.items()
            ],
        )


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


def main(source: str, overwrite: bool = False) -> None:
    """Import data from a SQLite database file into the application's database."""
    source_url = f"sqlite:///{source}"
    src_engine = create_engine(source_url, future=True)
    src = Session(src_engine)
    dst = SessionLocal()
    try:
        Base.metadata.create_all(bind=dst.get_bind())
        _ensure_animal_columns(dst)
        _ensure_image_columns(dst)
        metadata = MetaData()
        insp = inspect(src_engine)
        animal_table = Table("animal", metadata, autoload_with=src_engine)
        zoo_table = Table("zoo", metadata, autoload_with=src_engine)
        link_table = Table("zoo_animal", metadata, autoload_with=src_engine)
        image_table = variant_table = None
        if insp.has_table("image") and insp.has_table("image_variant"):
            image_table = Table("image", metadata, autoload_with=src_engine)
            variant_table = Table("image_variant", metadata, autoload_with=src_engine)

        cat_map = _stage_categories(src, dst, animal_table)
        animal_map = _import_animals(src, dst, animal_table, cat_map, overwrite=overwrite)
        zoo_map = _import_zoos(src, dst, zoo_table)
        if image_table is not None and variant_table is not None:
            _import_images(
                src,
                dst,
                image_table,
                variant_table,
                animal_map,
                overwrite=overwrite,
            )
        _import_links(src, dst, link_table, zoo_map, animal_map)
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import data from a SQLite dump")
    parser.add_argument("source", help="Path to source SQLite database")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing field values with those from the source",
    )
    args = parser.parse_args()
    main(args.source, overwrite=args.overwrite)
