class TestPostProcessedAgentData:
    async def test_creates_records_returns_201(self, client, sample_payload):
        response = await client.post("/processed_agent_data/", json=sample_payload)
        assert response.status_code == 201

    async def test_response_contains_generated_id(self, client, sample_payload):
        response = await client.post("/processed_agent_data/", json=sample_payload)
        data = response.json()
        assert len(data) == 1
        assert "id" in data[0]

    async def test_response_contains_correct_road_state(self, client, sample_payload):
        response = await client.post("/processed_agent_data/", json=sample_payload)
        assert response.json()[0]["road_state"] == "good"

    async def test_empty_list_returns_empty_response(self, client):
        response = await client.post("/processed_agent_data/", json=[])
        assert response.status_code == 201
        assert response.json() == []

    async def test_invalid_road_state_returns_422(self, client):
        bad_payload = [
            {
                "road_state": "flying",
                "agent_data": {
                    "accelerometer": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "gps": {"latitude": 0.0, "longitude": 0.0},
                    "time": "2026-03-19T10:00:00Z",
                },
            }
        ]
        response = await client.post("/processed_agent_data/", json=bad_payload)
        assert response.status_code == 422

    async def test_missing_field_returns_422(self, client):
        response = await client.post("/processed_agent_data/", json=[{"road_state": "good"}])
        assert response.status_code == 422

    async def test_batch_of_three_all_saved(self, client):
        payload = [
            {
                "road_state": state,
                "agent_data": {
                    "accelerometer": {"x": 1.0, "y": 0.5, "z": 9.8},
                    "gps": {"latitude": 50.45, "longitude": 30.52},
                    "time": "2026-03-19T10:00:00Z",
                },
            }
            for state in ("good", "bad", "warning")
        ]
        response = await client.post("/processed_agent_data/", json=payload)
        assert response.status_code == 201
        assert len(response.json()) == 3


class TestGetAllProcessedAgentData:
    async def test_empty_db_returns_empty_list(self, client):
        response = await client.get("/processed_agent_data/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_previously_posted_records(self, client, sample_payload):
        await client.post("/processed_agent_data/", json=sample_payload)
        response = await client.get("/processed_agent_data/")
        assert len(response.json()) == 1

    async def test_returns_all_records(self, client):
        payload = [
            {
                "road_state": state,
                "agent_data": {
                    "accelerometer": {"x": 1.0, "y": 0.5, "z": 9.8},
                    "gps": {"latitude": 50.0, "longitude": 30.0},
                    "time": "2026-03-19T10:00:00Z",
                },
            }
            for state in ("good", "bad")
        ]
        await client.post("/processed_agent_data/", json=payload)
        response = await client.get("/processed_agent_data/")
        assert len(response.json()) == 2


class TestGetByIdProcessedAgentData:
    async def test_returns_correct_record(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        response = await client.get(f"/processed_agent_data/{record_id}")
        assert response.status_code == 200
        assert response.json()["id"] == record_id

    async def test_missing_id_returns_404(self, client):
        response = await client.get("/processed_agent_data/99999")
        assert response.status_code == 404

    async def test_response_schema_complete(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        data = (await client.get(f"/processed_agent_data/{record_id}")).json()
        for field in ("id", "road_state", "x", "y", "z", "latitude", "longitude", "timestamp"):
            assert field in data, f"Відсутнє поле: {field}"


class TestUpdateProcessedAgentData:
    async def test_updates_road_state(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        updated = sample_payload[0].copy()
        updated["road_state"] = "bad"
        response = await client.put(f"/processed_agent_data/{record_id}", json=updated)
        assert response.status_code == 200
        assert response.json()["road_state"] == "bad"

    async def test_missing_id_returns_404(self, client, sample_payload):
        response = await client.put("/processed_agent_data/99999", json=sample_payload[0])
        assert response.status_code == 404

    async def test_subsequent_get_reflects_update(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        updated = sample_payload[0].copy()
        updated["road_state"] = "good"
        await client.put(f"/processed_agent_data/{record_id}", json=updated)
        get_resp = await client.get(f"/processed_agent_data/{record_id}")
        assert get_resp.json()["road_state"] == "good"


class TestDeleteProcessedAgentData:
    async def test_deletes_existing_record(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        del_resp = await client.delete(f"/processed_agent_data/{record_id}")
        assert del_resp.status_code == 200

    async def test_deleted_record_not_found_afterwards(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        await client.delete(f"/processed_agent_data/{record_id}")
        get_resp = await client.get(f"/processed_agent_data/{record_id}")
        assert get_resp.status_code == 404

    async def test_missing_id_returns_404(self, client):
        response = await client.delete("/processed_agent_data/99999")
        assert response.status_code == 404

    async def test_returns_deleted_object(self, client, sample_payload):
        post_resp = await client.post("/processed_agent_data/", json=sample_payload)
        record_id = post_resp.json()[0]["id"]
        del_resp = await client.delete(f"/processed_agent_data/{record_id}")
        assert del_resp.json()["id"] == record_id


class TestHealth:
    async def test_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_returns_ok_status(self, client):
        response = await client.get("/health")
        assert response.json() == {"status": "ok"}
