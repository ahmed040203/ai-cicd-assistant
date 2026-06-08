
import pytest

from fastapi.testclient import TestClient

import os

os.environ["TESTING"] = "true"

from main import app

client = TestClient(app)

def test_health():

    response = client.get("/health")

    assert response.status_code == 200

def test_create_order():

    response = client.post("/api/orders", json={

        "user_id": "test-user",

        "items": [{"product_id": "p1", "quantity": 1, "price": 10.0}]

    })

    assert response.status_code in [200, 201, 422]

