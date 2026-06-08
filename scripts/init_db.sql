-- AI CI/CD Assistant Database Init

CREATE DATABASE users_db;
CREATE DATABASE products_db;
CREATE DATABASE orders_db;
CREATE DATABASE payments_db;
CREATE DATABASE ai_cicd_db;

\c ai_cicd_db;

-- Pipeline analysis results
CREATE TABLE IF NOT EXISTS pipeline_analyses (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(32) NOT NULL,
    service_name VARCHAR(64) NOT NULL,
    pipeline_name VARCHAR(128),
    failed_stage VARCHAR(64),
    build_number INTEGER,
    analysis JSONB,
    raw_logs_preview TEXT,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    duration_ms INTEGER
);

-- Scaling recommendations
CREATE TABLE IF NOT EXISTS scaling_recommendations (
    id VARCHAR(64) PRIMARY KEY,
    service_name VARCHAR(64) NOT NULL,
    metrics JSONB,
    recommendation JSONB,
    applied BOOLEAN DEFAULT FALSE,
    analyzed_at TIMESTAMP DEFAULT NOW()
);

-- Anomaly detections
CREATE TABLE IF NOT EXISTS anomaly_detections (
    id VARCHAR(64) PRIMARY KEY,
    service_name VARCHAR(64) NOT NULL,
    metric_name VARCHAR(64),
    current_value FLOAT,
    baseline_value FLOAT,
    deviation_percent FLOAT,
    is_anomaly BOOLEAN,
    ai_analysis JSONB,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pipeline_analyses_service ON pipeline_analyses(service_name);
CREATE INDEX idx_pipeline_analyses_date ON pipeline_analyses(analyzed_at DESC);
CREATE INDEX idx_anomalies_service ON anomaly_detections(service_name);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
