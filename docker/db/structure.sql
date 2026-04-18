CREATE TABLE IF NOT EXISTS processed_agent_data (
    id SERIAL PRIMARY KEY,
    road_state VARCHAR(32) NOT NULL,
    x FLOAT NOT NULL,
    y FLOAT NOT NULL,
    z FLOAT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

-- Універсальна таблиця для показань довільних сенсорів (Lab 6).
CREATE TABLE IF NOT EXISTS sensor_readings (
    id SERIAL PRIMARY KEY,
    sensor_id VARCHAR(128) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_id ON sensor_readings (sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_type ON sensor_readings (sensor_type);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings (timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_payload_gin ON sensor_readings USING GIN (payload);
