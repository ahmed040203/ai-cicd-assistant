import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_list_products():
    res = client.get("/api/products")
    assert res.status_code == 200
    assert len(res.json()["products"]) > 0

def test_get_product():
    res = client.get("/api/products/1")
    assert res.status_code == 200
    assert res.json()["id"] == "1"

def test_get_product_not_found():
    res = client.get("/api/products/9999")
    assert res.status_code == 404

def test_create_product():
    res = client.post("/api/products", json={
        "name": "Test Item", "price": 9.99, "stock": 10,
        "category": "test", "description": "Test product"
    })
    assert res.status_code == 201
    assert res.json()["name"] == "Test Item"

def test_filter_by_category():
    res = client.get("/api/products?category=electronics")
    assert res.status_code == 200
    for p in res.json()["products"]:
        assert p["category"] == "electronics"

def test_reserve_stock():
    res = client.post("/api/products/1/reserve?quantity=2")
    assert res.status_code == 200
    assert res.json()["reserved"] == 2

def test_reserve_insufficient_stock():
    res = client.post("/api/products/1/reserve?quantity=999999")
    assert res.status_code == 400

def test_search_products():
    res = client.get("/api/products/search/Laptop")
    assert res.status_code == 200
    assert res.json()["count"] > 0
