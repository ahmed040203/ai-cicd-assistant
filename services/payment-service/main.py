from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum
import logging, json, time, random, os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Service", version="1.0.0")

FAILURE_RATE = float(os.getenv("PAYMENT_FAILURE_RATE", "0.05"))  # 5% failure by default

class PaymentStatus(str, Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    refunded = "refunded"

class PaymentRequest(BaseModel):
    order_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    payment_method: str = "card"
    card_last4: Optional[str] = "4242"

class RefundRequest(BaseModel):
    reason: Optional[str] = "Customer request"

payments_db: dict = {}

def mock_payment_gateway(amount: float, card_last4: str) -> tuple[bool, str]:
    """Mock Stripe-like payment processing"""
    # Simulate specific failure cards
    if card_last4 == "0002":
        return False, "Card declined"
    if card_last4 == "0341":
        return False, "Insufficient funds"
    # Random failure based on FAILURE_RATE
    if random.random() < FAILURE_RATE:
        return False, "Payment gateway timeout"
    return True, "Payment processed successfully"

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "payment-service",
        "timestamp": datetime.utcnow().isoformat(),
        "total_payments": len(payments_db),
        "failure_rate": FAILURE_RATE
    }

@app.post("/api/payments/charge", status_code=201)
def charge(payment: PaymentRequest):
    start = time.time()
    payment_id = f"PAY-{int(time.time())}-{random.randint(1000, 9999)}"

    # Simulate processing time
    time.sleep(random.uniform(0.1, 0.5))

    success, message = mock_payment_gateway(payment.amount, payment.card_last4 or "4242")

    status = PaymentStatus.success if success else PaymentStatus.failed
    transaction_id = f"TXN-{random.randint(100000, 999999)}" if success else None

    record = {
        "payment_id": payment_id,
        "order_id": payment.order_id,
        "user_id": payment.user_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": status,
        "transaction_id": transaction_id,
        "message": message,
        "card_last4": payment.card_last4,
        "created_at": datetime.utcnow().isoformat(),
        "duration_ms": round((time.time()-start)*1000)
    }
    payments_db[payment_id] = record

    logger.info(json.dumps({
        "event": "payment_processed", "payment_id": payment_id,
        "order_id": payment.order_id, "amount": payment.amount,
        "status": status, "duration_ms": record["duration_ms"]
    }))

    if not success:
        logger.error(json.dumps({
            "event": "payment_failed", "payment_id": payment_id,
            "order_id": payment.order_id, "reason": message
        }))
        raise HTTPException(status_code=402, detail={"message": message, "payment_id": payment_id})

    return record

@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str):
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@app.get("/api/payments/order/{order_id}")
def get_payment_by_order(order_id: str):
    payments = [p for p in payments_db.values() if p["order_id"] == order_id]
    return {"payments": payments, "count": len(payments)}

@app.post("/api/payments/{payment_id}/refund")
def refund(payment_id: str, refund_req: RefundRequest):
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment["status"] != PaymentStatus.success:
        raise HTTPException(status_code=400, detail="Only successful payments can be refunded")

    payment["status"] = PaymentStatus.refunded
    payment["refund_reason"] = refund_req.reason
    payment["refunded_at"] = datetime.utcnow().isoformat()

    logger.info(json.dumps({"event": "payment_refunded", "payment_id": payment_id, "amount": payment["amount"]}))
    return {"message": "Refund processed", "payment_id": payment_id, "amount": payment["amount"]}
