from sqlalchemy import text
from sqlalchemy.engine import Engine


def create_triggers(engine: Engine) -> None:
    """Create database triggers to keep zoo visits in sync with sightings."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            conn.execute(
                text(
                    """
                    CREATE OR REPLACE FUNCTION sighting_date(ts timestamptz)
                    RETURNS date
                    LANGUAGE SQL IMMUTABLE
                    AS $$ SELECT (ts AT TIME ZONE 'UTC')::date $$;
                    """
                )
            )
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_sightings_user_zoo_date
                  ON animal_sightings (user_id, zoo_id, date(sighting_datetime));
                """
            )
        stmts = [
            """
            CREATE TRIGGER IF NOT EXISTS animal_sighting_insert
            AFTER INSERT ON animal_sightings
            BEGIN
                INSERT OR IGNORE INTO zoo_visits(id, user_id, zoo_id, visit_date)
                VALUES (gen_random_uuid(), NEW.user_id, NEW.zoo_id, date(NEW.sighting_datetime));
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS animal_sighting_delete
            AFTER DELETE ON animal_sightings
            BEGIN
                DELETE FROM zoo_visits
                WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id AND visit_date=date(OLD.sighting_datetime)
                  AND NOT EXISTS (
                    SELECT 1 FROM animal_sightings
                    WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id
                      AND date(sighting_datetime)=date(OLD.sighting_datetime)
                  );
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS animal_sighting_update
            AFTER UPDATE ON animal_sightings
            BEGIN
                INSERT OR IGNORE INTO zoo_visits(id, user_id, zoo_id, visit_date)
                VALUES (gen_random_uuid(), NEW.user_id, NEW.zoo_id, date(NEW.sighting_datetime));
                DELETE FROM zoo_visits
                WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id AND visit_date=date(OLD.sighting_datetime)
                  AND NOT EXISTS (
                    SELECT 1 FROM animal_sightings
                    WHERE user_id=OLD.user_id AND zoo_id=OLD.zoo_id
                      AND date(sighting_datetime)=date(OLD.sighting_datetime)
                  );
            END;
            """,
        ]
        with engine.begin() as conn:
            for stmt in stmts:
                conn.exec_driver_sql(stmt)
    elif engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_sightings_user_zoo_date
                      ON animal_sightings (user_id, zoo_id, sighting_date(sighting_datetime));
                    """
                )
            )
        stmts = [
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
        ]
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(text(stmt))
    else:
        # other databases are not supported
        pass

