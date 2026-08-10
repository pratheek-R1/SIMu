-- PostgreSQL schema.
--
-- On Render the API creates these itself at first boot via SQLAlchemy metadata.
-- Running this by hand is still preferable when provisioning a database
-- yourself: it makes the shape of the data reviewable, and it adds the indexes
-- and RLS posture that create_all does not.
--
-- Row Level Security is enabled and left with NO permissive policies. The API
-- connects as the owning role, which bypasses RLS; anything else added later
-- gets no access until a policy is written for it. Session rows carry thesis
-- and telemetry data that determine a student's grade, so the default must be
-- deny.

create extension if not exists "uuid-ossp";

-- ---------------------------------------------------------------------------
create table if not exists cohorts (
    id          uuid primary key default uuid_generate_v4(),
    name        varchar(160) not null unique,
    seed        integer      not null,
    is_active   boolean      not null default true,
    created_at  timestamptz  not null default now()
);

-- ---------------------------------------------------------------------------
create table if not exists users (
    id               uuid primary key default uuid_generate_v4(),
    email            varchar(320) not null unique,
    hashed_password  varchar(200) not null,
    name             varchar(160) not null default 'Analyst',
    photo_url        text,
    role             varchar(24)  not null default 'student'
                     check (role in ('student', 'facilitator')),
    cohort_id        uuid references cohorts(id) on delete set null,
    created_at       timestamptz  not null default now()
);
create index if not exists idx_users_cohort on users(cohort_id);

-- ---------------------------------------------------------------------------
create table if not exists sessions (
    id                      uuid primary key default uuid_generate_v4(),
    user_id                 uuid not null references users(id) on delete cascade,
    cohort_id               uuid references cohorts(id) on delete set null,
    seed                    integer     not null,
    dataset_fingerprint     varchar(32) not null,

    status                  varchar(24) not null default 'active',
    current_screen          varchar(24) not null default 'brief',
    furthest_screen         varchar(24) not null default 'brief',

    -- Immutable once thesis_locked is true. Enforced in the API; a student who
    -- can revise after seeing the archive has not taken this test.
    thesis_locked           boolean     not null default false,
    thesis_variables        jsonb,
    thesis_confidence       jsonb,
    falsification           text,
    thesis_locked_at        timestamptz,

    committee_answers       jsonb,
    deliberation_started_at timestamptz,

    archive_unlocked        boolean     not null default false,
    archive_unlocked_at     timestamptz,

    -- The pre-revision weight snapshot. Revision Quality is measured against it.
    w1_snapshot             jsonb,
    model_weights           jsonb,

    picks                   jsonb,
    -- Cheque size per pick in whole USD, keyed by deal id as text. Null means
    -- the pool was never sized and is split evenly across the picks.
    cheque_sizes            jsonb,
    deployed                boolean     not null default false,
    deployed_at             timestamptz,
    fund_result             jsonb,

    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now(),
    completed_at            timestamptz
);
create index if not exists idx_sessions_user   on sessions(user_id);
create index if not exists idx_sessions_cohort on sessions(cohort_id);
create index if not exists idx_sessions_status on sessions(status);

-- ---------------------------------------------------------------------------
-- Append-only behavioural log. Every point on a scorecard traces to a row here,
-- which is what makes a grade defensible to a student who disputes it.
create table if not exists telemetry_events (
    id          bigserial primary key,
    session_id  uuid not null references sessions(id) on delete cascade,
    kind        varchar(48) not null,
    subject     varchar(64),
    payload     jsonb,
    screen      varchar(24),
    created_at  timestamptz not null default now()
);
create index if not exists idx_events_session on telemetry_events(session_id);
create index if not exists idx_events_kind    on telemetry_events(session_id, kind);

-- ---------------------------------------------------------------------------
create table if not exists scorecards (
    id          uuid primary key default uuid_generate_v4(),
    session_id  uuid not null unique references sessions(id) on delete cascade,
    total       double precision not null,
    band        varchar(24)      not null,
    dimensions  jsonb            not null,
    created_at  timestamptz      not null default now()
);

-- ---------------------------------------------------------------------------
create table if not exists reports (
    id            uuid primary key default uuid_generate_v4(),
    -- One report per session. Without the constraint a repeated POST /report
    -- inserts a duplicate and every later read of it fails.
    session_id    uuid not null unique references sessions(id) on delete cascade,
    content_html  text,
    created_at    timestamptz not null default now()
);
create index if not exists idx_reports_session on reports(session_id);

-- ---------------------------------------------------------------------------
alter table cohorts          enable row level security;
alter table users            enable row level security;
alter table sessions         enable row level security;
alter table telemetry_events enable row level security;
alter table scorecards       enable row level security;
alter table reports          enable row level security;

-- No policies are defined on purpose. Reads and writes go through the API. If
-- you ever grant another role direct access to this database, write its
-- policies before doing so -- not after.
