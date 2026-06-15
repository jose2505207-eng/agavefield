-- =============================================================================
-- Agave Field Copilot — full database schema for Supabase / PostgreSQL
-- Paste this whole file into the Supabase SQL Editor and click "Run".
-- Idempotent: safe to run more than once (CREATE ... IF NOT EXISTS).
-- Mirrors app/models/database.py exactly (column names must match the ORM).
-- =============================================================================

-- 1) users -------------------------------------------------------------------
create table if not exists users (
  id                serial primary key,
  full_name         varchar(255),
  telegram_user_id  varchar(64) unique,
  whatsapp_phone    varchar(32),
  role              varchar(32) default 'agronomist',
  created_at        timestamp default now(),
  updated_at        timestamp default now()
);
create index if not exists ix_users_telegram on users(telegram_user_id);
create index if not exists ix_users_whatsapp on users(whatsapp_phone);

-- 2) farms -------------------------------------------------------------------
create table if not exists farms (
  id            serial primary key,
  name          varchar(255) not null,
  municipality  varchar(128),
  state         varchar(128) default 'Jalisco',
  owner_name    varchar(255),
  notes         text,
  created_at    timestamp default now(),
  updated_at    timestamp default now()
);

-- 3) lots --------------------------------------------------------------------
create table if not exists lots (
  id                    serial primary key,
  farm_id               integer references farms(id),
  lot_code              varchar(64) not null,
  crop_type             varchar(64) default 'agave_azul',
  planted_at            timestamp,
  estimated_age_months  integer,
  polygon_geojson       jsonb,
  centroid_latitude     double precision,
  centroid_longitude    double precision,
  notes                 text,
  created_at            timestamp default now(),
  updated_at            timestamp default now()
);
create index if not exists ix_lots_farm on lots(farm_id);
create index if not exists ix_lots_code on lots(lot_code);

-- 4) field_zones -------------------------------------------------------------
create table if not exists field_zones (
  id                  serial primary key,
  lot_id              integer references lots(id),
  zone_name           varchar(64) not null,
  centroid_latitude   double precision,
  centroid_longitude  double precision,
  notes               text,
  created_at          timestamp default now(),
  updated_at          timestamp default now()
);
create index if not exists ix_zones_lot on field_zones(lot_id);
create index if not exists ix_zones_name on field_zones(zone_name);

-- 5) agave_passports ---------------------------------------------------------
create table if not exists agave_passports (
  id                    serial primary key,
  passport_code         varchar(64) unique not null,
  farm_id               integer references farms(id),
  lot_id                integer references lots(id),
  zone_id               integer references field_zones(id),
  label                 varchar(255),
  field_name            varchar(255),
  lot_name              varchar(255),
  zone_name             varchar(255),
  latitude              double precision,
  longitude             double precision,
  estimated_age_months  integer,
  health_status         varchar(32) default 'unknown',
  risk_level            varchar(16) default 'unknown',
  last_inspection_at    timestamp,
  next_inspection_at    timestamp,
  notes                 text,
  created_at            timestamp default now(),
  updated_at            timestamp default now()
);
create index if not exists ix_passports_farm on agave_passports(farm_id);
create index if not exists ix_passports_lot  on agave_passports(lot_id);
create index if not exists ix_passports_zone on agave_passports(zone_id);
create index if not exists ix_passports_risk on agave_passports(risk_level);

-- 6) field_observations ------------------------------------------------------
create table if not exists field_observations (
  id                        serial primary key,
  user_id                   integer references users(id),
  farm_id                   integer references farms(id),
  lot_id                    integer references lots(id),
  passport_id               integer references agave_passports(id),
  source_channel            varchar(32) default 'telegram',
  image_url                 varchar(1024),
  thumbnail_url             varchar(1024),
  original_caption          text,
  latitude                  double precision,
  longitude                 double precision,
  observed_at               timestamp default now(),
  image_type                varchar(32) default 'unknown',
  plant_condition           varchar(32) default 'unknown',
  suspected_issue           varchar(255),
  diagnosis                 varchar(255),
  severity                  varchar(16) default 'unknown',
  confidence                double precision default 0,
  visible_symptoms_json     jsonb,
  ai_summary                text,
  recommended_next_step     text,
  needs_human_review        boolean default true,
  human_verified            boolean default false,
  human_correction          text,
  human_validation_status   varchar(16) default 'pending',
  human_corrected_label     varchar(255),
  human_notes               text,
  validated_by              varchar(128),
  validated_at              timestamp,
  status                    varchar(32) default 'new',
  escalation_status         varchar(32) default 'none',
  created_at                timestamp default now(),
  updated_at                timestamp default now()
);
create index if not exists ix_obs_user      on field_observations(user_id);
create index if not exists ix_obs_farm      on field_observations(farm_id);
create index if not exists ix_obs_lot       on field_observations(lot_id);
create index if not exists ix_obs_passport  on field_observations(passport_id);
create index if not exists ix_obs_observed  on field_observations(observed_at);
create index if not exists ix_obs_severity  on field_observations(severity);
create index if not exists ix_obs_status    on field_observations(status);
create index if not exists ix_obs_escstatus on field_observations(escalation_status);
create index if not exists ix_obs_valstatus on field_observations(human_validation_status);

-- 7) model_outputs (immutable AI inference log) ------------------------------
create table if not exists model_outputs (
  id              serial primary key,
  observation_id  integer references field_observations(id) on delete cascade,
  model_name      varchar(128) not null,
  raw_json        jsonb not null,
  confidence      double precision default 0,
  created_at      timestamp default now()
);
create index if not exists ix_model_obs on model_outputs(observation_id);

-- 8) weather_snapshots -------------------------------------------------------
create table if not exists weather_snapshots (
  id                serial primary key,
  observation_id    integer references field_observations(id) on delete cascade,
  latitude          double precision,
  longitude         double precision,
  temperature_c     double precision,
  humidity_percent  double precision,
  precipitation_mm  double precision,
  wind_speed_kmh    double precision,
  recent_rain_mm    double precision,
  heat_risk         varchar(16),
  drought_risk      varchar(16),
  weather_source    varchar(64),
  raw_json          jsonb,
  created_at        timestamp default now()
);
create index if not exists ix_weather_obs on weather_snapshots(observation_id);

-- 9) escalations -------------------------------------------------------------
create table if not exists escalations (
  id                 serial primary key,
  observation_id     integer references field_observations(id) on delete cascade,
  channel            varchar(32) not null,
  recipient          varchar(128) not null,
  escalation_reason  text,
  message_body       text,
  status             varchar(32) default 'pending',
  sent_at            timestamp,
  created_at         timestamp default now()
);
create index if not exists ix_esc_obs on escalations(observation_id);

-- 10) tasks ------------------------------------------------------------------
create table if not exists tasks (
  id              serial primary key,
  passport_id     integer references agave_passports(id),
  observation_id  integer references field_observations(id),
  title           varchar(255) not null,
  description     text,
  priority        varchar(16) default 'medium',     -- low|medium|high|urgent
  status          varchar(16) default 'open',       -- open|in_progress|completed|cancelled
  assigned_to     varchar(128),
  due_date        timestamp,
  source          varchar(24) default 'ai_generated', -- ai_generated|human_created|weather_trigger|follow_up
  needs_approval  boolean default false,
  approved        boolean default false,
  created_at      timestamp default now(),
  updated_at      timestamp default now()
);
create index if not exists ix_tasks_passport on tasks(passport_id);
create index if not exists ix_tasks_obs      on tasks(observation_id);
create index if not exists ix_tasks_status   on tasks(status);
create index if not exists ix_tasks_due      on tasks(due_date);

-- 11) alerts -----------------------------------------------------------------
create table if not exists alerts (
  id               serial primary key,
  passport_id      integer references agave_passports(id),
  observation_id   integer references field_observations(id),
  recipient        varchar(128),
  channel          varchar(32) default 'dashboard',  -- whatsapp|telegram|dashboard|console
  title            varchar(255) not null,
  message          text,
  severity         varchar(16) default 'medium',
  reason           varchar(255),
  delivery_status  varchar(16) default 'pending',
  read             boolean default false,
  created_at       timestamp default now()
);
create index if not exists ix_alerts_passport on alerts(passport_id);
create index if not exists ix_alerts_obs      on alerts(observation_id);
create index if not exists ix_alerts_severity on alerts(severity);
create index if not exists ix_alerts_created  on alerts(created_at);

-- 12) human_validations (training-quality feedback, immutable) ---------------
create table if not exists human_validations (
  id                   serial primary key,
  observation_id       integer references field_observations(id) on delete cascade,
  status               varchar(16) not null,          -- confirmed|corrected|rejected
  original_diagnosis   varchar(255),
  corrected_label      varchar(255),
  original_confidence  double precision,
  notes                text,
  validated_by         varchar(128),
  created_at           timestamp default now()
);
create index if not exists ix_val_obs on human_validations(observation_id);

-- 13) weekly_reports ---------------------------------------------------------
create table if not exists weekly_reports (
  id            serial primary key,
  scope_type    varchar(16) default 'all',  -- all|farm|lot|zone
  scope_id      integer,
  period_start  timestamp not null,
  period_end    timestamp not null,
  payload_json  jsonb not null,
  created_at    timestamp default now()
);

-- =============================================================================
-- No seed/demo data. This is a production schema — the database starts empty
-- and is populated only by real field uploads. Add real farms/lots via the API
-- or dashboard (POST /lots) when you have actual field boundaries.
-- =============================================================================
