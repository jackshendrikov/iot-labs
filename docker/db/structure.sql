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