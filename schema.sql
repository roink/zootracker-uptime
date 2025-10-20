-- Enable UUID generation (PostgreSQL pgcrypto extension)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable PostGIS for geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;
-- Enable trigram search support
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- Enable accent-insensitive comparisons
CREATE EXTENSION IF NOT EXISTS unaccent;
-- Enable case-insensitive text comparisons
CREATE EXTENSION IF NOT EXISTS citext;

CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS
$$ SELECT public.unaccent('public.unaccent', $1) $$;

-- 1. Users
CREATE TABLE users (
  id              UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  email           CITEXT NOT NULL UNIQUE,
  password_hash   VARCHAR(255) NOT NULL,
  email_verified_at TIMESTAMPTZ,
  last_login_at   TIMESTAMPTZ,
  last_active_at  TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 1b. Refresh tokens
CREATE TABLE refresh_tokens (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash        CHAR(64) NOT NULL UNIQUE,
  family_id         UUID NOT NULL,
  issued_at         TIMESTAMPTZ NOT NULL,
  expires_at        TIMESTAMPTZ NOT NULL,
  last_used_at      TIMESTAMPTZ NOT NULL,
  rotated_at        TIMESTAMPTZ,
  revoked_at        TIMESTAMPTZ,
  revocation_reason TEXT,
  user_agent        TEXT
);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens (family_id);
CREATE INDEX ix_refresh_tokens_revoked_at ON refresh_tokens (revoked_at);
CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens (expires_at);

-- 1c. Verification tokens
CREATE TABLE verification_tokens (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose      VARCHAR(64) NOT NULL,
  token_hash   VARCHAR(128) NOT NULL,
  code_hash    VARCHAR(128),
  expires_at   TIMESTAMPTZ NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL,
  consumed_at  TIMESTAMPTZ
);

CREATE INDEX ix_verification_tokens_user_purpose ON verification_tokens (user_id, purpose);
CREATE INDEX ix_verification_tokens_active ON verification_tokens (user_id, purpose, consumed_at);

-- 2. Region reference tables
CREATE TABLE continent_names (
  id       INTEGER PRIMARY KEY,
  name_de  TEXT NOT NULL UNIQUE,
  name_en  TEXT
);

CREATE TABLE country_names (
  id            INTEGER PRIMARY KEY,
  name_de       TEXT NOT NULL UNIQUE,
  name_en       TEXT,
  continent_id  INTEGER REFERENCES continent_names(id)
);

-- 3. Zoos
CREATE TABLE zoos (
  id              UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  slug            TEXT NOT NULL,
  address         TEXT,
  latitude        DECIMAL(9,6),
  longitude       DECIMAL(9,6),
  location        GEOGRAPHY(POINT, 4326),
  continent_id    INTEGER REFERENCES continent_names(id),
  country_id      INTEGER REFERENCES country_names(id),
  city            TEXT,
  official_website TEXT,
  wikipedia_de    TEXT,
  wikipedia_en    TEXT,
  description_de  TEXT,
  description_en  TEXT,
  image_url       VARCHAR(512),
  animal_count    INTEGER NOT NULL DEFAULT 0 CHECK (animal_count >= 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_zoos_location_gist ON zoos USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_zoos_name_trgm
  ON zoos USING gin (f_unaccent(name) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_zoos_city_trgm
  ON zoos USING gin (f_unaccent(city) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_zoos_name_city_trgm
  ON zoos USING gin (
    f_unaccent(coalesce(name, '') || ' ' || coalesce(city, '')) gin_trgm_ops
  );
CREATE INDEX IF NOT EXISTS idx_zoos_country_id   ON zoos(country_id);
CREATE INDEX IF NOT EXISTS idx_zoos_continent_id ON zoos(continent_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_zoos_slug ON zoos(slug);


-- 3. Categories (e.g., Mammal, Bird, Reptile)
CREATE TABLE categories (
  id    UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name  VARCHAR(100) NOT NULL UNIQUE
);

-- 4. Taxon names for classes, orders and families
CREATE TABLE klasse_names (
  klasse INTEGER PRIMARY KEY,
  name_de TEXT,
  name_en TEXT
);

CREATE TABLE ordnung_names (
  ordnung INTEGER PRIMARY KEY,
  name_de TEXT,
  name_en TEXT
);

CREATE TABLE familie_names (
  familie INTEGER PRIMARY KEY,
  name_de TEXT,
  name_en TEXT
);

-- 5. Animals
CREATE TABLE animals (
  id                 UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  scientific_name    VARCHAR(255),
  category_id        UUID       NOT NULL REFERENCES categories(id),
  description        TEXT,
  description_de     TEXT,
  description_en     TEXT,
  conservation_state TEXT,
  name_fallback      TEXT,
  name_en            VARCHAR(255) NOT NULL,
  slug               TEXT NOT NULL,
  name_de            TEXT,
  art                INTEGER,
  parent_art         INTEGER,
  CONSTRAINT fk_animals_parent_art
      FOREIGN KEY (parent_art) REFERENCES animals(art) DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT ck_animals_parent_not_self CHECK (parent_art IS NULL OR parent_art <> art),
  CONSTRAINT uq_animals_art UNIQUE (art),
  english_label      TEXT,
  german_label       TEXT,
  latin_name         TEXT,
  klasse             INTEGER REFERENCES klasse_names(klasse),
  ordnung            INTEGER REFERENCES ordnung_names(ordnung),
  familie            INTEGER REFERENCES familie_names(familie),
  taxon_rank         TEXT,
  zoo_count          INTEGER NOT NULL DEFAULT 0 CHECK (zoo_count >= 0),
  default_image_url  TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_animals_zoo_count ON animals (zoo_count DESC);
CREATE INDEX IF NOT EXISTS idx_animals_parent_art ON animals (parent_art);
CREATE INDEX IF NOT EXISTS idx_animals_parent_art_name_en_id
    ON animals (parent_art, name_en, id);
CREATE INDEX IF NOT EXISTS idx_animal_popularity
    ON animals (zoo_count DESC, name_en ASC, id ASC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_animals_slug ON animals(slug);
CREATE INDEX IF NOT EXISTS idx_animals_klasse ON animals(klasse);
CREATE INDEX IF NOT EXISTS idx_animals_ordnung ON animals(ordnung);
CREATE INDEX IF NOT EXISTS idx_animals_familie ON animals(familie);
CREATE INDEX IF NOT EXISTS idx_animals_klasse_ordnung ON animals(klasse, ordnung);
CREATE INDEX IF NOT EXISTS idx_animals_ordnung_familie ON animals(ordnung, familie);

-- 6. Zoo ↔ Animal join table
CREATE TABLE zoo_animals (
  zoo_id     UUID NOT NULL REFERENCES zoos(id) ON DELETE CASCADE,
  animal_id  UUID NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  PRIMARY KEY (zoo_id, animal_id)
);
-- Indexes to support join-table lookups
CREATE INDEX IF NOT EXISTS idx_zooanimal_zoo_id ON zoo_animals(zoo_id);
CREATE INDEX IF NOT EXISTS idx_zooanimal_animal_id ON zoo_animals(animal_id);

CREATE TABLE user_favorite_zoos (
    user_id UUID NOT NULL,
    zoo_id UUID NOT NULL,
    PRIMARY KEY (user_id, zoo_id),
    CONSTRAINT fk_user_favorite_zoos_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_favorite_zoos_zoo FOREIGN KEY (zoo_id)
        REFERENCES zoos(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_userfavoritezoo_user_id ON user_favorite_zoos(user_id);
CREATE INDEX IF NOT EXISTS idx_userfavoritezoo_zoo_id ON user_favorite_zoos(zoo_id);

CREATE TABLE user_favorite_animals (
    user_id UUID NOT NULL,
    animal_id UUID NOT NULL,
    PRIMARY KEY (user_id, animal_id),
    CONSTRAINT fk_user_favorite_animals_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_favorite_animals_animal FOREIGN KEY (animal_id)
        REFERENCES animals(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_userfavoriteanimal_user_id ON user_favorite_animals(user_id);
CREATE INDEX IF NOT EXISTS idx_userfavoriteanimal_animal_id ON user_favorite_animals(animal_id);

-- 7. Zoo Visits
CREATE TABLE zoo_visits (
  id           UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  zoo_id       UUID       NOT NULL REFERENCES zoos(id) ON DELETE CASCADE,
  visit_date   DATE       NOT NULL,
  notes        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Composite index to accelerate visit lookups by user and zoo
CREATE INDEX IF NOT EXISTS idx_zoovisit_user_zoo ON zoo_visits (user_id, zoo_id);

-- 8. Animal Sightings
CREATE TABLE animal_sightings (
  id                  UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  zoo_id              UUID       NOT NULL REFERENCES zoos(id) ON DELETE CASCADE,
  animal_id           UUID       NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  sighting_datetime   TIMESTAMPTZ NOT NULL,
  notes               TEXT,
  photo_url           VARCHAR(512),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Index to accelerate user-specific sighting queries
CREATE INDEX IF NOT EXISTS idx_animalsighting_user_animal ON animal_sightings(user_id, animal_id);
CREATE INDEX IF NOT EXISTS idx_animalsighting_user_animal_datetime
  ON animal_sightings (user_id, animal_id, sighting_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_sightings_user_day_created
  ON animal_sightings (user_id, sighting_datetime DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sightings_user_zoo_datetime
  ON animal_sightings (user_id, zoo_id, sighting_datetime DESC, created_at DESC);


-- 8. Achievements / Badges
CREATE TABLE achievements (
  id           UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name         VARCHAR(255) NOT NULL UNIQUE,
  description  TEXT,
  criteria     TEXT,
  icon_url     VARCHAR(512),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. User Achievements
CREATE TABLE user_achievements (
  id             UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  achievement_id UUID       NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
  awarded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, achievement_id)
);

-- 10. Animal images (match app.models.Image / ImageVariant)
CREATE TABLE IF NOT EXISTS images (
  mid              TEXT PRIMARY KEY,
  animal_id        UUID NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  commons_title    TEXT,
  commons_page_url TEXT,
  original_url     TEXT NOT NULL,
  width            INTEGER NOT NULL,
  height           INTEGER NOT NULL,
  size_bytes       INTEGER NOT NULL,
  sha1             TEXT NOT NULL CHECK (length(sha1) = 40),
  mime             TEXT NOT NULL,
  uploaded_at      TIMESTAMP,
  uploader         TEXT,
  title            TEXT,
  artist_raw       TEXT,
  artist_plain     TEXT,
  license          TEXT,
  license_short    TEXT,
  license_url      TEXT,
  attribution_required BOOLEAN,
  usage_terms      TEXT,
  credit_line      TEXT,
  source           TEXT NOT NULL CHECK (source IN ('WIKIDATA_P18','WIKI_LEAD_DE','WIKI_LEAD_EN')),
  retrieved_at     TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_images_animal_id ON images (animal_id);
CREATE INDEX IF NOT EXISTS idx_images_sha1 ON images (sha1);
CREATE INDEX IF NOT EXISTS idx_images_source ON images (source);

CREATE TABLE IF NOT EXISTS image_variants (
  mid       TEXT NOT NULL REFERENCES images(mid) ON DELETE CASCADE,
  width     INTEGER NOT NULL,
  height    INTEGER NOT NULL,
  thumb_url TEXT NOT NULL,
  PRIMARY KEY (mid, width)
);
