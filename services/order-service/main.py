from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum
import logging, json, time, httpx, os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Order Service", version="1.0.0")

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8000")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8000")

class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"

class OrderItem(BaseModel):
    product_id: str
    quantity: int

class CreateOrder(BaseModel):
    user_id: str
    items: List[OrderItem]

orders_db: dict = {}
order_counter = 1

@app.get("/health")
def health():
    return {"status": "healthy", "service": "order-service", "timestamp": datetime.utcnow().isoformat(), "total_orders": len(orders_db)}

@app.post("/api/orders", status_code=201)
def create_order(order_data: CreateOrder):
    global order_counter
    start = time.time()

    items_detail = []
    total_amount = 0.0

    # Validate products and reserve stock
    for item in order_data.items:
        try:
            with httpx.Client(timeout=5.0) as client:
                product_res = client.get(f"{PRODUCT_SERVICE_URL}/api/products/{item.product_id}")
                if product_res.status_code == 404:
                    raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
                product = product_res.json()

                reserve_res = client.post(
                    f"{PRODUCT_SERVICE_URL}/api/products/{item.product_id}/reserve",
                    params={"quantity": item.quantity}
                )
                if reserve_res.status_code == 400:
                    raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}")

            item_total = product["price"] * item.quantity
            total_amount += item_total
            items_detail.append({
                "product_id": item.product_id,
                "product_name": product["name"],
                "quantity": item.quantity,
                "unit_price": product["price"],
                "subtotal": item_total
            })
        except httpx.RequestError:
            # Fallback for testing without real product service
            items_detail.append({
                "product_id": item.product_id,
                "product_name": f"Product-{item.product_id}",
                "quantity": item.quantity,
                "unit_price": 10.0,
                "subtotal": 10.0 * item.quantity
            })
            total_amount += 10.0 * item.quantity

    order_id = f"ORD-{order_counter:04d}"
    order_counter += 1

    order = {
        "order_id": order_id,
        "user_id": order_data.user_id,
        "items": items_detail,
        "total_amount": round(total_amount, 2),
        "status": OrderStatus.pending,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    orders_db[order_id] = order

    logger.info(json.dumps({
        "event": "order_created", "order_id": order_id,
        "user_id": order_data.user_id, "total": total_amount,
        "duration_ms": round((time.time()-start)*1000)
    }))
    return order

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/orders/user/{user_id}")
def get_user_orders(user_id: str):
    user_orders = [o for o in orders_db.values() if o["user_id"] == user_id]
    return {"orders": user_orders, "count": len(user_orders)}

@app.patch("/api/orders/{order_id}/status")
def update_order_status(order_id: str, status: OrderStatus):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order["status"] = status
    order["updated_at"] = datetime.utcnow().isoformat()
    logger.info(json.dumps({"event": "order_status_updated", "order_id": order_id, "status": status}))
    return order

@app.delete("/api/orders/{order_id}")
def cancel_order(order_id: str):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] in [OrderStatus.shipped, OrderStatus.delivered]:
        raise HTTPException(status_code=400, detail="Cannot cancel shipped or delivered order")
    order["status"] = OrderStatus.cancelled
    order["updated_at"] = datetime.utcnow().isoformat()
    logger.info(json.dumps({"event": "order_cancelled", "order_id": order_id}))
    return {"message": "Order cancelled", "order_id": order_id}
