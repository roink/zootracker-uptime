import argparse
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    select,
    func,
    bindparam,
    inspect,
    exists,
)

from app.db_extensions import ensure_pg_extensions
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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


logger = logging.getLogger(__name__)
BANNED_MIDS = {"M31984332", "M1723980", "M117776631", "M55041643"}


def _import_taxon_names(
    src: Session,
    dst: Session,
    klasse_table: Table | None,
    ordnung_table: Table | None,
    familie_table: Table | None,
) -> None:
    """Import class, order and family names if available."""

    if klasse_table is not None:
        rows = src.execute(select(klasse_table)).mappings()
        for row in rows:
            dst.merge(
                models.ClassName(
                    klasse=row.get("klasse"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    if ordnung_table is not None:
        rows = src.execute(select(ordnung_table)).mappings()
        for row in rows:
            dst.merge(
                models.OrderName(
                    ordnung=row.get("ordnung"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    if familie_table is not None:
        rows = src.execute(select(familie_table)).mappings()
        for row in rows:
            dst.merge(
                models.FamilyName(
                    familie=row.get("familie"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    # Make sure inserted taxon names are written before dependent rows
    dst.flush()


def _import_regions(
    src: Session,
    dst: Session,
    continent_table: Table | None,
    country_table: Table | None,
) -> None:
    """Import continent and country names."""

    if continent_table is not None:
        rows = src.execute(select(continent_table)).mappings()
        for row in rows:
            dst.merge(
                models.ContinentName(
                    id=row.get("id"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    if country_table is not None:
        rows = src.execute(select(country_table)).mappings()
        for row in rows:
            dst.merge(
                models.CountryName(
                    id=row.get("id"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                    continent_id=row.get("continent_id"),
                )
            )
    dst.flush()

def _stage_categories(
    src: Session,
    dst: Session,
    animal_table: Table,
    link_table: Table,
) -> Dict[int | None, uuid.UUID]:
    """Ensure a :class:`Category` exists for each distinct ``klasse`` value.

    Only categories for animals that appear in ``zoo_animal`` are created.
    """

    klasses_stmt = (
        select(animal_table.c.klasse)
        .where(
            exists(
                select(1)
                .select_from(link_table)
                .where(
                    link_table.c.art == animal_table.c.art,
                    link_table.c.art.isnot(None),
                    link_table.c.art != "",
                )
            )
        )
        .distinct()
    )
    klasses = [row["klasse"] for row in src.execute(klasses_stmt).mappings()]
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
    link_table: Table,
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
    rows_stmt = select(animal_table).where(
        exists(
            select(1)
            .select_from(link_table)
            .where(
                link_table.c.art == animal_table.c.art,
                link_table.c.art.isnot(None),
                link_table.c.art != "",
            )
        )
    )
    n_total_animals_in_src = src.execute(
        select(func.count()).select_from(animal_table)
    ).scalar_one()
    n_linked_animals = src.execute(
        rows_stmt.with_only_columns(func.count())
    ).scalar_one()
    rows = src.execute(rows_stmt).mappings()
    animals = []
    id_map: Dict[str, uuid.UUID] = {}
    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    for row in rows:
        art = row.get("art")
        # only import explicit description_de; ignore legacy zootierliste_description
        desc_de = _clean_text(row.get("description_de"))
        desc_en = _clean_text(row.get("description_en"))
        status = normalize_status(row.get("iucn_conservation_status"))
        taxon_rank = row.get("taxon_rank")
        if taxon_rank:
            taxon_rank = taxon_rank.strip()
        slug = row.get("slug")
        if isinstance(slug, str):
            slug = slug.strip() or None
        if slug is None and isinstance(art, str):
            fallback = re.sub(r"[^a-z0-9]+", "-", art.lower()).strip("-")
            slug = fallback or None
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
            if slug is not None:
                assign("slug", slug)
            if changed:
                dst.add(animal)
                n_updated += 1
            else:
                n_skipped += 1
            id_map[art] = aid
            continue
        if not row.get("latin_name") or not row.get("name_de"):
            logger.warning("Animal %s missing latin or German name", art)
        name_en = row.get("name_en") or row.get("latin_name") or art
        if slug is None:
            logger.warning("Skipping animal %s due to missing slug", art)
            n_skipped += 1
            continue
        aid = uuid.uuid4()
        animals.append(
            models.Animal(
                id=aid,
                scientific_name=row.get("latin_name"),
                slug=slug,
                name_de=row.get("name_de"),
                name_en=name_en,
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
        n_inserted += 1
    if animals:
        dst.bulk_save_objects(animals)
    n_skipped = n_linked_animals - n_inserted - n_updated
    logger.info(
        "Animal import: total=%d linked=%d inserted=%d updated=%d skipped=%d",
        n_total_animals_in_src,
        n_linked_animals,
        n_inserted,
        n_updated,
        n_skipped,
    )
    return id_map


def _import_zoos(src: Session, dst: Session, zoo_table: Table) -> Dict[int, uuid.UUID]:
    """Insert zoos and build id mapping."""

    existing_rows = list(
        dst.execute(
            select(
                models.Zoo.id,
                models.Zoo.name,
                models.Zoo.city,
                models.Zoo.country_id,
                models.Zoo.slug,
            )
        ).mappings()
    )
    existing_by_key: Dict[tuple[str, str, int | None], uuid.UUID] = {}
    existing_by_slug: Dict[str, uuid.UUID] = {}
    seen_slugs: set[str] = set()
    for row in existing_rows:
        key = (row["name"], row["city"], row["country_id"])
        existing_by_key[key] = row["id"]
        slug = row.get("slug")
        if slug:
            existing_by_slug[slug] = row["id"]
            seen_slugs.add(slug)

    def ensure_unique_slug(candidate: str) -> str:
        """Ensure ``candidate`` slug is unique by appending a numeric suffix."""

        base = candidate or "zoo"
        slug = base
        suffix = 2
        while slug in seen_slugs:
            slug = f"{base}-{suffix}"
            suffix += 1
        seen_slugs.add(slug)
        return slug

    rows = list(src.execute(select(zoo_table)).mappings())
    zoos = []
    mapping: Dict[int, uuid.UUID] = {}
    for row in rows:
        key: tuple[str, str, int | None] = (
            row.get("name"),
            row.get("city"),
            row.get("country"),
        )
        slug = row.get("slug")
        if isinstance(slug, str):
            slug = slug.strip() or None
        if not slug:
            base_name = row.get("name") or ""
            city = row.get("city") or ""
            base = f"{base_name}-{city}" if city else base_name
            if not base:
                base = f"zoo-{row.get('zoo_id')}"
            slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
            if not slug:
                slug = f"zoo-{row.get('zoo_id')}"
        slug = slug[:255]
        desc_en = _clean_text(row.get("description_en"))
        desc_de = _clean_text(row.get("description_de"))
        zid = existing_by_slug.get(slug)
        if zid is not None:
            if desc_en or desc_de:
                z = dst.get(models.Zoo, zid)
                changed = False
                if desc_en and z.description_en != desc_en:
                    z.description_en = desc_en
                    changed = True
                if desc_de and z.description_de != desc_de:
                    z.description_de = desc_de
                    changed = True
                if changed:
                    dst.add(z)
            mapping[row["zoo_id"]] = zid
            seen_slugs.add(slug)
            existing_by_key[key] = zid
            continue
        if key in existing_by_key:
            zid = existing_by_key[key]
            z = dst.get(models.Zoo, zid)
            changed = False
            if desc_en or desc_de:
                if desc_en and z.description_en != desc_en:
                    z.description_en = desc_en
                    changed = True
                if desc_de and z.description_de != desc_de:
                    z.description_de = desc_de
                    changed = True
            current_slug = z.slug
            if current_slug and existing_by_slug.get(current_slug) == zid:
                existing_by_slug.pop(current_slug, None)
            if slug in seen_slugs:
                new_slug = ensure_unique_slug(slug)
            else:
                new_slug = slug
                seen_slugs.add(new_slug)
            if z.slug != new_slug:
                z.slug = new_slug
                changed = True
            existing_by_slug[new_slug] = zid
            if changed:
                dst.add(z)
            mapping[row["zoo_id"]] = zid
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
        if slug in seen_slugs:
            unique_slug = ensure_unique_slug(slug)
        else:
            unique_slug = slug
            seen_slugs.add(unique_slug)
        existing_by_slug[unique_slug] = zid
        zoos.append(
            models.Zoo(
                id=zid,
                name=row.get("name"),
                slug=unique_slug,
                continent_id=row.get("continent"),
                country_id=row.get("country"),
                city=row.get("city"),
                description_en=desc_en,
                description_de=desc_de,
                latitude=lat,
                longitude=lon,
            )
        )
        mapping[row["zoo_id"]] = zid
        existing_by_key[key] = zid
    if zoos:
        dst.bulk_save_objects(zoos)
    return mapping


def _import_images(
    src: Session,
    dst: Session,
    image_table: Table,
    variant_table: Table,
    animal_map: Dict[str, uuid.UUID],
    overwrite: bool = False,
) -> None:
    """Insert images and thumbnail variants."""

    img_rows = list(src.execute(select(image_table)).mappings())
    images: list[models.Image] = []
    mid_to_animal: Dict[str, uuid.UUID] = {}
    existing = {img.mid: img for img in dst.execute(select(models.Image)).scalars()}
    for row in img_rows:
        mid = row.get("mid")
        if mid in BANNED_MIDS:
            continue
        aid = animal_map.get(row.get("animal_art"))
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
            logger.warning("Skipping image %s due to invalid metadata", mid)
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
        mid = row.get("mid")
        # Skip variants for banned images or those skipped earlier due to invalid metadata
        if mid in BANNED_MIDS or mid not in mid_to_animal:
            continue
        key = (mid, row.get("width"))
        if key in existing_vars:
            continue
        variants.append(
            models.ImageVariant(
                mid=mid,
                width=row.get("width"),
                height=row.get("height"),
                thumb_url=row.get("thumb_url"),
            )
        )
        aid = mid_to_animal.get(mid)
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
        stmt = sqlite_insert(models.ZooAnimal.__table__).on_conflict_do_nothing()
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
        engine = dst.get_bind()
        ensure_pg_extensions(engine)
        Base.metadata.create_all(bind=engine)
        _ensure_animal_columns(dst)
        _ensure_image_columns(dst)
        metadata = MetaData()
        insp = inspect(src_engine)
        # Reflect required tables; images are optional
        animal_table = Table("animal", metadata, autoload_with=src_engine)
        zoo_table = Table("zoo", metadata, autoload_with=src_engine)
        link_table = Table("zoo_animal", metadata, autoload_with=src_engine)
        image_table = variant_table = None
        if insp.has_table("image") and insp.has_table("image_variant"):
            image_table = Table("image", metadata, autoload_with=src_engine)
            variant_table = Table("image_variant", metadata, autoload_with=src_engine)
        klasse_table = ordnung_table = familie_table = None
        if insp.has_table("klasse_name"):
            klasse_table = Table("klasse_name", metadata, autoload_with=src_engine)
        if insp.has_table("ordnung_name"):
            ordnung_table = Table("ordnung_name", metadata, autoload_with=src_engine)
        if insp.has_table("familie_name"):
            familie_table = Table("familie_name", metadata, autoload_with=src_engine)
        continent_table = country_table = None
        if insp.has_table("continent_name"):
            continent_table = Table("continent_name", metadata, autoload_with=src_engine)
        if insp.has_table("country_name"):
            country_table = Table("country_name", metadata, autoload_with=src_engine)

        with dst.begin() as trans:
            _import_taxon_names(src, dst, klasse_table, ordnung_table, familie_table)
            _import_regions(src, dst, continent_table, country_table)
            # Ensure FK parents exist before bulk inserting animals
            dst.flush()
            cat_map = _stage_categories(src, dst, animal_table, link_table)
            animal_map = _import_animals(
                src, dst, animal_table, link_table, cat_map, overwrite=overwrite
            )
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
