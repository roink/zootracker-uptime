"""Database trigger management helpers."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

_PRE_TRIGGER_STATEMENTS: tuple[str, ...] = (
    """
    CREATE OR REPLACE FUNCTION sighting_date(ts timestamptz)
    RETURNS date
    LANGUAGE SQL IMMUTABLE
    AS $$ SELECT (ts AT TIME ZONE 'UTC')::date $$;
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_sightings_user_zoo_date
      ON animal_sightings (user_id, zoo_id, sighting_date(sighting_datetime));
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sightings_user_day_created
      ON animal_sightings (user_id, sighting_datetime DESC, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sightings_user_zoo_datetime
      ON animal_sightings (user_id, zoo_id, sighting_datetime DESC, created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_zoo_animals_zoo_id ON zoo_animals(zoo_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_zoo_animals_animal_id ON zoo_animals(animal_id);
    """,
)

_TRIGGER_STATEMENTS: tuple[str, ...] = (
    """
    CREATE OR REPLACE FUNCTION sync_zoo_visits()
    RETURNS TRIGGER AS $$
    BEGIN
        IF TG_OP = 'INSERT' THEN
            INSERT INTO zoo_visits(user_id, zoo_id, visit_date)
            VALUES (NEW.user_id, NEW.zoo_id, sighting_date(NEW.sighting_datetime))
            ON CONFLICT (user_id, zoo_id, visit_date) DO NOTHING;
            RETURN NEW;
        ELSIF TG_OP = 'UPDATE' THEN
            IF (NEW.user_id, NEW.zoo_id, sighting_date(NEW.sighting_datetime)) !=
               (OLD.user_id, OLD.zoo_id, sighting_date(OLD.sighting_datetime)) THEN
                IF NOT EXISTS (
                    SELECT 1 FROM animal_sightings
                    WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id
                      AND sighting_date(sighting_datetime)=sighting_date(OLD.sighting_datetime)
                ) THEN
                    DELETE FROM zoo_visits
                    WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id AND visit_date=sighting_date(OLD.sighting_datetime);
                END IF;
                INSERT INTO zoo_visits(user_id, zoo_id, visit_date)
                VALUES (NEW.user_id, NEW.zoo_id, sighting_date(NEW.sighting_datetime))
                ON CONFLICT (user_id, zoo_id, visit_date) DO NOTHING;
            END IF;
            RETURN NEW;
        ELSIF TG_OP = 'DELETE' THEN
            IF NOT EXISTS (
                SELECT 1 FROM animal_sightings
                WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id
                  AND sighting_date(sighting_datetime)=sighting_date(OLD.sighting_datetime)
            ) THEN
                DELETE FROM zoo_visits
                WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id AND visit_date=sighting_date(OLD.sighting_datetime);
            END IF;
            RETURN OLD;
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    """,
    """
    DROP TRIGGER IF EXISTS sync_zoo_visits_trigger ON animal_sightings;
    """,
    """
    CREATE TRIGGER sync_zoo_visits_trigger
    AFTER INSERT OR UPDATE OR DELETE ON animal_sightings
    FOR EACH ROW EXECUTE FUNCTION sync_zoo_visits();
    """,
    """
    CREATE OR REPLACE FUNCTION update_zoo_animal_counts()
    RETURNS TRIGGER AS $$
    BEGIN
        IF TG_OP = 'INSERT' THEN
            UPDATE animals SET zoo_count = (SELECT COUNT(*) FROM zoo_animals WHERE animal_id = NEW.animal_id)
            WHERE id = NEW.animal_id;
            UPDATE zoos SET animal_count = (SELECT COUNT(*) FROM zoo_animals WHERE zoo_id = NEW.zoo_id)
            WHERE id = NEW.zoo_id;
            RETURN NEW;
        ELSIF TG_OP = 'DELETE' THEN
            UPDATE animals SET zoo_count = (SELECT COUNT(*) FROM zoo_animals WHERE animal_id = OLD.animal_id)
            WHERE id = OLD.animal_id;
            UPDATE zoos SET animal_count = (SELECT COUNT(*) FROM zoo_animals WHERE zoo_id = OLD.zoo_id)
            WHERE id = OLD.zoo_id;
            RETURN OLD;
        ELSE
            IF NEW.animal_id <> OLD.animal_id THEN
                UPDATE animals SET zoo_count = (SELECT COUNT(*) FROM zoo_animals WHERE animal_id = OLD.animal_id) WHERE id = OLD.animal_id;
                UPDATE animals SET zoo_count = (SELECT COUNT(*) FROM zoo_animals WHERE animal_id = NEW.animal_id) WHERE id = NEW.animal_id;
            END IF;
            IF NEW.zoo_id <> OLD.zoo_id THEN
                UPDATE zoos SET animal_count = (SELECT COUNT(*) FROM zoo_animals WHERE zoo_id = OLD.zoo_id) WHERE id = OLD.zoo_id;
                UPDATE zoos SET animal_count = (SELECT COUNT(*) FROM zoo_animals WHERE zoo_id = NEW.zoo_id) WHERE id = NEW.zoo_id;
            END IF;
            RETURN NEW;
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS zoo_animals_count_trigger ON zoo_animals;",
    """
    CREATE TRIGGER zoo_animals_count_trigger
    AFTER INSERT OR UPDATE OR DELETE ON zoo_animals
    FOR EACH ROW EXECUTE FUNCTION update_zoo_animal_counts();
    """,
)


def _execute_statements(conn: Connection, statements: Iterable[str]) -> None:
    for stmt in statements:
        conn.execute(text(stmt))


def _ensure_postgresql(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":  # pragma: no cover - defensive guardrail
        raise RuntimeError("PostgreSQL/PostGIS is required")


def _apply_triggers(conn: Connection) -> None:
    _ensure_postgresql(conn)
    if conn.in_transaction():
        _execute_statements(conn, _PRE_TRIGGER_STATEMENTS)
        _execute_statements(conn, _TRIGGER_STATEMENTS)
        return

    with conn.begin():
        _execute_statements(conn, _PRE_TRIGGER_STATEMENTS)
        _execute_statements(conn, _TRIGGER_STATEMENTS)


def create_triggers(bind: Engine | Connection) -> None:
    """Create database triggers to sync visits and maintain count columns."""

    if isinstance(bind, Engine):
        with bind.connect() as conn:
            _apply_triggers(conn)
    else:
        _apply_triggers(bind)
