def test_config_lists_supported_choices(client):
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    body = response.json()
    assert set(body["time_controls"]) == {"3+2", "5+0", "10+0", "15+10"}
    assert body["difficulties"]["medium"]["skill"] == 7
    assert body["csrf_token"]


def test_mutation_requires_csrf(client):
    response = client.post(
        "/api/v1/games",
        json={"color": "white", "difficulty": "medium", "time_control": "10+0"},
    )
    assert response.status_code == 403


def test_create_game_and_submit_legal_move(csrf_client):
    client, headers = csrf_client
    created = client.post(
        "/api/v1/games",
        headers=headers,
        json={"color": "white", "difficulty": "medium", "time_control": "10+0"},
    )
    assert created.status_code == 201
    game = created.json()
    assert game["player_color"] == "white"
    assert game["pending_ai"] is False

    moved = client.post(
        f"/api/v1/games/{game['id']}/moves",
        headers=headers,
        json={
            "uci": "e2e4",
            "expected_ply": 0,
            "expected_version": 1,
            "idempotency_key": "test-e2e4-0001",
        },
    )
    assert moved.status_code == 202
    body = moved.json()
    assert body["ply"] == 1
    assert body["moves"][0]["san"] == "e4"
    assert body["pending_ai"] is True


def test_rejects_illegal_and_stale_moves(csrf_client):
    client, headers = csrf_client
    game = client.post(
        "/api/v1/games",
        headers=headers,
        json={"color": "white", "difficulty": "easy", "time_control": "5+0"},
    ).json()
    illegal = client.post(
        f"/api/v1/games/{game['id']}/moves",
        headers=headers,
        json={
            "uci": "e2e5",
            "expected_ply": 0,
            "expected_version": 1,
            "idempotency_key": "illegal-0001",
        },
    )
    assert illegal.status_code == 422

    stale = client.post(
        f"/api/v1/games/{game['id']}/moves",
        headers=headers,
        json={
            "uci": "e2e4",
            "expected_ply": 2,
            "expected_version": 9,
            "idempotency_key": "stale-000001",
        },
    )
    assert stale.status_code == 409


def test_session_cannot_read_another_sessions_game(client):
    first_config = client.get("/api/v1/config").json()
    game = client.post(
        "/api/v1/games",
        headers={"X-CSRF-Token": first_config["csrf_token"]},
        json={"color": "white", "difficulty": "medium", "time_control": "10+0"},
    ).json()
    client.cookies.clear()
    client.get("/api/v1/config")
    assert client.get(f"/api/v1/games/{game['id']}").status_code == 404

