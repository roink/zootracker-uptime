-- Enable UUID generation (PostgreSQL pgcrypto extension)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable PostGIS for geospatial queries
CREATE EXTENSION IF NOT EXISTS postgis;
-- Enable trigram search support
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Users
CREATE TABLE users (
  id              UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  email           VARCHAR(255) NOT NULL UNIQUE,
  password_hash   VARCHAR(64) NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Zoos
CREATE TABLE zoos (
  id              UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  default_label   TEXT,
  label_en        TEXT,
  label_de        TEXT,
  address         TEXT,
  latitude        DECIMAL(9,6),
  longitude       DECIMAL(9,6),
  location        GEOGRAPHY(POINT, 4326),
  country         TEXT,
  city            TEXT,
  continent       TEXT,
  official_website TEXT,
  wikipedia_de    TEXT,
  wikipedia_en    TEXT,
  description_de  TEXT,
  description_en  TEXT,
  description     TEXT,
  image_url       VARCHAR(512),
  animal_count    INTEGER NOT NULL DEFAULT 0 CHECK (animal_count >= 0),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_zoos_location_gist ON zoos USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_zoos_name_trgm
  ON zoos USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_zoos_city_trgm
  ON zoos USING gin (city gin_trgm_ops);


-- 3. Categories (e.g., Mammal, Bird, Reptile)
CREATE TABLE categories (
  id    UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name  VARCHAR(100) NOT NULL UNIQUE
);

-- 4. Animals
CREATE TABLE animals (
  id                 UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  common_name        VARCHAR(255) NOT NULL,
  scientific_name    VARCHAR(255),
  category_id        UUID       NOT NULL REFERENCES categories(id),
  description        TEXT,
  description_de     TEXT,
  description_en     TEXT,
  conservation_state TEXT,
  name_fallback      TEXT,
  name_en            TEXT,
  name_de            TEXT,
  art                TEXT,
  english_label      TEXT,
  german_label       TEXT,
  latin_name         TEXT,
  klasse             INTEGER,
  ordnung            INTEGER,
  familie            INTEGER,
  taxon_rank         TEXT,
  zoo_count          INTEGER NOT NULL DEFAULT 0 CHECK (zoo_count >= 0),
  default_image_url  VARCHAR(512),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_animals_zoo_count ON animals (zoo_count DESC);

-- 5. Zoo ↔ Animal join table
CREATE TABLE zoo_animals (
  zoo_id     UUID NOT NULL REFERENCES zoos(id) ON DELETE CASCADE,
  animal_id  UUID NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  PRIMARY KEY (zoo_id, animal_id)
);
-- Indexes to support join-table lookups
CREATE INDEX IF NOT EXISTS idx_zooanimal_zoo_id ON zoo_animals(zoo_id);
CREATE INDEX IF NOT EXISTS idx_zooanimal_animal_id ON zoo_animals(animal_id);

-- 6. Zoo Visits
CREATE TABLE zoo_visits (
  id           UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  zoo_id       UUID       NOT NULL REFERENCES zoos(id) ON DELETE CASCADE,
  visit_date   DATE       NOT NULL,
  notes        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Index to accelerate /visits endpoint lookups by user
CREATE INDEX IF NOT EXISTS idx_zoo_visits_user_id ON zoo_visits(user_id);

-- 7. Animal Sightings
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
CREATE INDEX IF NOT EXISTS idx_sightings_user_animal ON animal_sightings(user_id, animal_id);

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
  source           TEXT
);

CREATE INDEX IF NOT EXISTS idx_images_animal_id ON images (animal_id);

CREATE TABLE IF NOT EXISTS image_variants (
  mid       TEXT NOT NULL REFERENCES images(mid) ON DELETE CASCADE,
  width     INTEGER NOT NULL,
  height    INTEGER NOT NULL,
  thumb_url TEXT NOT NULL,
  PRIMARY KEY (mid, width)
);
