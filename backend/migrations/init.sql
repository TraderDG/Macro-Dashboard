-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ─── macro_indicators ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS macro_indicators (
    id            BIGSERIAL,
    time          TIMESTAMPTZ       NOT NULL,
    country_code  VARCHAR(3)        NOT NULL,
    indicator     VARCHAR(64)       NOT NULL,
    value         DOUBLE PRECISION,
    unit          VARCHAR(32),
    source        VARCHAR(32)       NOT NULL,
    created_at    TIMESTAMPTZ       DEFAULT NOW(),
    CONSTRAINT uq_macro_point UNIQUE (time, country_code, indicator, source)
);

SELECT create_hypertable('macro_indicators', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_macro_country_indicator ON macro_indicators (country_code, indicator);

-- ─── yield_curves ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS yield_curves (
    id            BIGSERIAL,
    time          TIMESTAMPTZ       NOT NULL,
    country_code  VARCHAR(3)        NOT NULL DEFAULT 'USA',
    maturity      VARCHAR(8)        NOT NULL,
    yield_pct     DOUBLE PRECISION,
    created_at    TIMESTAMPTZ       DEFAULT NOW(),
    CONSTRAINT uq_yield_point UNIQUE (time, country_code, maturity)
);

SELECT create_hypertable('yield_curves', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_yield_time ON yield_curves (time DESC);

-- ─── market_prices ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_prices (
    id            BIGSERIAL,
    time          TIMESTAMPTZ       NOT NULL,
    symbol        VARCHAR(32)       NOT NULL,
    asset_class   VARCHAR(16)       NOT NULL,
    open          DOUBLE PRECISION,
    high          DOUBLE PRECISION,
    low           DOUBLE PRECISION,
    close         DOUBLE PRECISION,
    volume        DOUBLE PRECISION,
    source        VARCHAR(32)       DEFAULT 'yfinance',
    created_at    TIMESTAMPTZ       DEFAULT NOW(),
    CONSTRAINT uq_price_point UNIQUE (time, symbol)
);

SELECT create_hypertable('market_prices', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_price_symbol_time ON market_prices (symbol, time DESC);

-- ─── ingestion_logs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_logs (
    id               BIGSERIAL PRIMARY KEY,
    source           VARCHAR(32)  NOT NULL,
    indicator        VARCHAR(64)  NOT NULL,
    last_fetched_at  TIMESTAMPTZ  DEFAULT NOW(),
    records_upserted INT          DEFAULT 0,
    status           VARCHAR(16)  DEFAULT 'success',
    error_msg        TEXT,
    CONSTRAINT uq_ingestion_log UNIQUE (source, indicator)
);

-- ─── sentiment_indicators ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sentiment_indicators (
    id          BIGSERIAL,
    time        TIMESTAMPTZ   NOT NULL,
    indicator   VARCHAR(64)   NOT NULL,
    value       DOUBLE PRECISION,
    label       VARCHAR(32),
    source      VARCHAR(32)   NOT NULL,
    created_at  TIMESTAMPTZ   DEFAULT NOW(),
    CONSTRAINT uq_sentiment_point UNIQUE (time, indicator, source)
);

SELECT create_hypertable('sentiment_indicators', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_sentiment_time ON sentiment_indicators (time DESC);

-- ─── economic_events ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS economic_events (
    id          BIGSERIAL PRIMARY KEY,
    event_date  TIMESTAMPTZ   NOT NULL,
    event_name  VARCHAR(128)  NOT NULL,
    country     VARCHAR(8)    NOT NULL DEFAULT 'USA',
    importance  VARCHAR(8)    NOT NULL DEFAULT 'medium',
    actual      VARCHAR(32),
    forecast    VARCHAR(32),
    previous    VARCHAR(32),
    source      VARCHAR(32)   NOT NULL,
    created_at  TIMESTAMPTZ   DEFAULT NOW(),
    CONSTRAINT uq_event UNIQUE (event_date, event_name, country)
);

CREATE INDEX IF NOT EXISTS ix_event_date ON economic_events (event_date);

-- ─── news_headlines ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS news_headlines (
    id           BIGSERIAL PRIMARY KEY,
    title        TEXT         NOT NULL,
    url          TEXT,
    source       VARCHAR(64),
    published_at TIMESTAMPTZ,
    query_tag    VARCHAR(64),
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_news_published_at ON news_headlines (published_at DESC);

-- TimescaleDB compression policies (optional, saves ~90% disk space after 7 days)
-- ALTER TABLE macro_indicators SET (timescaledb.compress, timescaledb.compress_orderby = 'time DESC');
-- SELECT add_compression_policy('macro_indicators', INTERVAL '7 days');
