from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging, json, time, os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Product Service", version="1.0.0")

# In-memory store (replace with PostgreSQL + Redis)
products_db: dict = {
    "1": {"id": "1", "name": "Laptop Pro", "price": 999.99, "stock": 50, "category": "electronics", "description": "High-performance laptop"},
    "2": {"id": "2", "name": "Wireless Mouse", "price": 29.99, "stock": 200, "category": "electronics", "description": "Ergonomic wireless mouse"},
    "3": {"id": "3", "name": "Coffee Mug", "price": 12.99, "stock": 500, "category": "kitchen", "description": "Ceramic coffee mug"},
    "4": {"id": "4", "name": "Python Book", "price": 49.99, "stock": 100, "category": "books", "description": "Learn Python programming"},
    "5": {"id": "5", "name": "USB-C Hub", "price": 39.99, "stock": 75, "category": "electronics", "description": "7-in-1 USB-C hub"},
}

class Product(BaseModel):
    name: str
    price: float
    stock: int
    category: str
    description: Optional[str] = ""

class ProductUpdate(BaseModel):
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "healthy", "service": "product-service", "timestamp": datetime.utcnow().isoformat(), "total_products": len(products_db)}

@app.get("/api/products")
def list_products(
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    in_stock: Optional[bool] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0)
):
    start = time.time()
    results = list(products_db.values())
    if category:
        results = [p for p in results if p["category"] == category]
    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]
    if in_stock is not None:
        results = [p for p in results if (p["stock"] > 0) == in_stock]
    total = len(results)
    results = results[offset:offset + limit]
    logger.info(json.dumps({"event": "products_listed", "count": len(results), "duration_ms": round((time.time()-start)*1000)}))
    return {"products": results, "total": total, "limit": limit, "offset": offset}

@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    product = products_db.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.post("/api/products", status_code=201)
def create_product(product: Product):
    new_id = str(len(products_db) + 1)
    products_db[new_id] = {"id": new_id, **product.model_dump(), "created_at": datetime.utcnow().isoformat()}
    logger.info(json.dumps({"event": "product_created", "product_id": new_id, "name": product.name}))
    return products_db[new_id]

@app.patch("/api/products/{product_id}")
def update_product(product_id: str, update: ProductUpdate):
    product = products_db.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if update.price is not None:
        product["price"] = update.price
    if update.stock is not None:
        product["stock"] = update.stock
    if update.description is not None:
        product["description"] = update.description
    logger.info(json.dumps({"event": "product_updated", "product_id": product_id}))
    return product

@app.post("/api/products/{product_id}/reserve")
def reserve_stock(product_id: str, quantity: int):
    product = products_db.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product["stock"] < quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Available: {product['stock']}")
    product["stock"] -= quantity
    logger.info(json.dumps({"event": "stock_reserved", "product_id": product_id, "quantity": quantity, "remaining": product["stock"]}))
    return {"product_id": product_id, "reserved": quantity, "remaining_stock": product["stock"]}

@app.get("/api/products/search/{query}")
def search_products(query: str):
    results = [p for p in products_db.values() if query.lower() in p["name"].lower() or query.lower() in p["description"].lower()]
    return {"results": results, "count": len(results)}
