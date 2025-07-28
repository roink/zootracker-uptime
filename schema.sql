-- Enable UUID generation (PostgreSQL pgcrypto extension)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Optional: enable PostGIS for geospatial queries
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Users
CREATE TABLE users (
  id              UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  email           VARCHAR(255) NOT NULL UNIQUE,
  -- Bcrypt salts are over 50 characters so allow ample space
  password_salt   VARCHAR(64) NOT NULL,
  password_hash   VARCHAR(64) NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Zoos
CREATE TABLE zoos (
  id              UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,
  address         TEXT,
  latitude        DECIMAL(9,6),
  longitude       DECIMAL(9,6),
  description     TEXT,
  image_url       VARCHAR(512),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
  default_image_url  VARCHAR(512),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Zoo ↔ Animal join table
CREATE TABLE zoo_animals (
  zoo_id     UUID NOT NULL REFERENCES zoos(id) ON DELETE CASCADE,
  animal_id  UUID NOT NULL REFERENCES animals(id) ON DELETE CASCADE,
  PRIMARY KEY (zoo_id, animal_id)
);

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
