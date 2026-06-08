
import pytest

from fastapi.testclient import TestClient

import os

os.environ["TESTING"] = "true"

from main import app

client = TestClient(app)

def test_health():

    response = client.get("/health")

    assert response.status_code == 200

def test_charge():

    response = client.post("/api/payments/charge", json={

        "order_id": "test-order",

        "amount": 100.0,

        "currency": "USD"

    })

    assert response.status_code in [200, 201, 422]

