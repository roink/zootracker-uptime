"""CLI utility for importing data from a lightweight SQLite dump."""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.orm import Session

from app.db_extensions import ensure_pg_extensions

from .database import Base, SessionLocal
from .import_utils import _ensure_animal_columns, _ensure_image_columns
from .importers import (
    import_animals,
    import_images,
    import_links,
    import_regions,
    import_taxon_names,
    import_zoos,
    stage_categories,
)

logger = logging.getLogger(__name__)


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
            import_taxon_names(src, dst, klasse_table, ordnung_table, familie_table)
            import_regions(src, dst, continent_table, country_table)
            dst.flush()
            category_map = stage_categories(src, dst, animal_table, link_table)
            animal_map = import_animals(
                src,
                dst,
                animal_table,
                link_table,
                category_map,
                overwrite=overwrite,
            )
            zoo_map = import_zoos(src, dst, zoo_table)
            if image_table is not None and variant_table is not None:
                import_images(
                    src,
                    dst,
                    image_table,
                    variant_table,
                    animal_map,
                    overwrite=overwrite,
                )
            import_links(src, dst, link_table, zoo_map, animal_map)
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
