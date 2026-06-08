from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum
import logging, json, time, os, boto3

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Notification Service", version="1.0.0")

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

class NotificationType(str, Enum):
    order_confirmed = "order_confirmed"
    payment_success = "payment_success"
    payment_failed = "payment_failed"
    order_shipped = "order_shipped"
    order_delivered = "order_delivered"
    pipeline_alert = "pipeline_alert"

class NotificationRequest(BaseModel):
    recipient_email: str
    notification_type: NotificationType
    subject: str
    body: str
    metadata: Optional[dict] = {}

notifications_db: List[dict] = []

TEMPLATES = {
    NotificationType.order_confirmed: {
        "subject": "Order Confirmed - {order_id}",
        "body": "Your order {order_id} has been confirmed. Total: ${amount}"
    },
    NotificationType.payment_success: {
        "subject": "Payment Successful",
        "body": "Your payment of ${amount} was processed successfully. Transaction ID: {transaction_id}"
    },
    NotificationType.payment_failed: {
        "subject": "Payment Failed",
        "body": "Your payment of ${amount} failed. Reason: {reason}. Please try again."
    },
    NotificationType.pipeline_alert: {
        "subject": "CI/CD Pipeline Alert - {service}",
        "body": "Pipeline for {service} has {status}. AI Analysis: {ai_suggestion}"
    }
}

def send_email_mock(to: str, subject: str, body: str) -> bool:
    """Mock email sending — in production uses AWS SES"""
    logger.info(json.dumps({
        "event": "email_sent",
        "to": to,
        "subject": subject,
        "body_preview": body[:100]
    }))
    return True

def process_notification_background(notification: dict):
    """Background task to process and send notification"""
    time.sleep(0.1)  # Simulate processing
    success = send_email_mock(
        notification["recipient_email"],
        notification["subject"],
        notification["body"]
    )
    notification["sent"] = success
    notification["sent_at"] = datetime.utcnow().isoformat()
    notification["status"] = "sent" if success else "failed"

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "notification-service",
        "timestamp": datetime.utcnow().isoformat(),
        "total_notifications": len(notifications_db)
    }

@app.post("/api/notifications/send", status_code=202)
def send_notification(notification: NotificationRequest, background_tasks: BackgroundTasks):
    record = {
        "id": f"NOTIF-{int(time.time())}-{len(notifications_db)}",
        "recipient_email": notification.recipient_email,
        "notification_type": notification.notification_type,
        "subject": notification.subject,
        "body": notification.body,
        "metadata": notification.metadata,
        "status": "queued",
        "sent": False,
        "created_at": datetime.utcnow().isoformat(),
        "sent_at": None
    }
    notifications_db.append(record)
    background_tasks.add_task(process_notification_background, record)

    logger.info(json.dumps({
        "event": "notification_queued",
        "id": record["id"],
        "type": notification.notification_type,
        "recipient": notification.recipient_email
    }))
    return {"message": "Notification queued", "notification_id": record["id"]}

@app.post("/api/notifications/order-confirmed")
def order_confirmed_notification(order_id: str, user_email: str, amount: float, background_tasks: BackgroundTasks):
    template = TEMPLATES[NotificationType.order_confirmed]
    return send_notification(NotificationRequest(
        recipient_email=user_email,
        notification_type=NotificationType.order_confirmed,
        subject=template["subject"].format(order_id=order_id),
        body=template["body"].format(order_id=order_id, amount=amount),
        metadata={"order_id": order_id}
    ), background_tasks)

@app.post("/api/notifications/pipeline-alert")
def pipeline_alert(service: str, status: str, ai_suggestion: str, background_tasks: BackgroundTasks):
    """Called by AI engine to notify about pipeline issues"""
    template = TEMPLATES[NotificationType.pipeline_alert]
    return send_notification(NotificationRequest(
        recipient_email=os.getenv("ALERT_EMAIL", "devops-team@example.com"),
        notification_type=NotificationType.pipeline_alert,
        subject=template["subject"].format(service=service),
        body=template["body"].format(service=service, status=status, ai_suggestion=ai_suggestion),
        metadata={"service": service, "pipeline_status": status}
    ), background_tasks)

@app.get("/api/notifications")
def list_notifications(limit: int = 50):
    return {"notifications": notifications_db[-limit:], "total": len(notifications_db)}
