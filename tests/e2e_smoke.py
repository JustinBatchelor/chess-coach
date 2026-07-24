"""Black-box smoke test for a running Chess Coach web and worker pair."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from http.cookiejar import CookieJar

BASE_URL = os.environ.get("CHESS_COACH_URL", "http://127.0.0.1:8080")


def main() -> None:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if method != "GET":
            headers["X-CSRF-Token"] = csrf
        req = urllib.request.Request(
            f"{BASE_URL}{path}", data=body, headers=headers, method=method
        )
        with opener.open(req, timeout=10) as response:
            return json.load(response)

    config = request("/api/v1/config")
    csrf = config["csrf_token"]
    game = request(
        "/api/v1/games",
        "POST",
        {"color": "black", "difficulty": "beginner", "time_control": "10+0"},
    )
    deadline = time.monotonic() + 15
    while game["pending_ai"] and time.monotonic() < deadline:
        time.sleep(0.25)
        game = request(f"/api/v1/games/{game['id']}")
    assert game["ply"] == 1 and not game["pending_ai"], game

    game = request(f"/api/v1/games/{game['id']}/resign", "POST")
    assert game["status"] == "completed" and game["review_id"], game
    deadline = time.monotonic() + 30
    review = request(f"/api/v1/reviews/{game['review_id']}")
    while review["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.25)
        review = request(f"/api/v1/reviews/{game['review_id']}")
    assert review["status"] == "complete", review
    assert len(review["results"]) == 1, review
    print(
        json.dumps(
            {
                "game_id": game["id"],
                "computer_move": game["moves"][0]["san"],
                "review_status": review["status"],
                "classification": review["results"][0]["classification"],
            }
        )
    )


if __name__ == "__main__":
    main()
