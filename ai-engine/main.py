from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging, json, time, os, boto3, httpx
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="AI CI/CD Assistant Engine", version="1.0.0")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")

# In-memory store for AI analysis results
analysis_db: List[dict] = []

# ─────────────────────────────────────────
# Bedrock Client
# ─────────────────────────────────────────
def get_bedrock_client():
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)

def call_bedrock(prompt: str, system_prompt: str = "") -> str:
    """Call AWS Bedrock with Claude model"""
    try:
        client = get_bedrock_client()
        messages = [{"role": "user", "content": prompt}]
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": messages
        }
        if system_prompt:
            body["system"] = system_prompt

        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except ClientError as e:
        logger.error(f"Bedrock error: {e}")
        return f"[AI Engine] Bedrock unavailable: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected Bedrock error: {e}")
        return f"[AI Engine] Error calling AI: {str(e)}"

# ─────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────
class PipelineFailureEvent(BaseModel):
    pipeline_name: str
    service_name: str
    failed_stage: str
    error_logs: str
    build_number: int
    branch: str = "main"
    commit_sha: Optional[str] = None

class MetricsEvent(BaseModel):
    service_name: str
    cpu_percent: float
    memory_percent: float
    request_rate: float
    error_rate: float
    avg_response_time_ms: float
    period_minutes: int = 5

class AnomalyEvent(BaseModel):
    service_name: str
    metric_name: str
    current_value: float
    baseline_value: float
    threshold_percent: float = 50.0

# ─────────────────────────────────────────
# AI: Log Analyzer + Fix Suggester
# ─────────────────────────────────────────
@app.post("/api/ai/analyze-failure")
def analyze_pipeline_failure(event: PipelineFailureEvent, background_tasks: BackgroundTasks):
    start = time.time()

    system_prompt = """You are an expert DevOps AI assistant specializing in CI/CD pipelines, Docker, and AWS.
Your job is to analyze pipeline failures and provide clear, actionable fixes.
Always respond in JSON format with these exact fields:
- root_cause: string (1-2 sentences explaining WHY it failed)
- severity: string (one of: critical, high, medium, low)
- fix_steps: array of strings (ordered steps to fix the issue)
- code_fix: string (actual code/command to run, if applicable)
- prevention: string (how to prevent this in the future)
- estimated_fix_time: string (e.g., "5 minutes", "1 hour")"""

    prompt = f"""Analyze this CI/CD pipeline failure and provide a fix:

Service: {event.service_name}
Pipeline: {event.pipeline_name}
Failed Stage: {event.failed_stage}
Branch: {event.branch}
Build Number: #{event.build_number}

Error Logs:
```
{event.error_logs}
```

Respond ONLY with valid JSON, no markdown, no explanation outside the JSON."""

    ai_response = call_bedrock(prompt, system_prompt)

    try:
        analysis = json.loads(ai_response)
    except json.JSONDecodeError:
        analysis = {
            "root_cause": ai_response[:500],
            "severity": "high",
            "fix_steps": ["Review the error logs manually", "Check service dependencies"],
            "code_fix": "",
            "prevention": "Add better error handling",
            "estimated_fix_time": "Unknown"
        }

    record = {
        "id": f"ANALYSIS-{int(time.time())}",
        "type": "pipeline_failure",
        "service_name": event.service_name,
        "pipeline_name": event.pipeline_name,
        "failed_stage": event.failed_stage,
        "build_number": event.build_number,
        "analysis": analysis,
        "raw_logs_preview": event.error_logs[:300],
        "analyzed_at": datetime.utcnow().isoformat(),
        "duration_ms": round((time.time()-start)*1000)
    }
    analysis_db.append(record)

    logger.info(json.dumps({
        "event": "failure_analyzed", "service": event.service_name,
        "severity": analysis.get("severity"), "duration_ms": record["duration_ms"]
    }))

    # Send notification in background
    background_tasks.add_task(notify_pipeline_failure, event, analysis)

    return record

# ─────────────────────────────────────────
# AI: Scaling Advisor
# ─────────────────────────────────────────
@app.post("/api/ai/scaling-advice")
def get_scaling_advice(metrics: MetricsEvent):
    start = time.time()

    system_prompt = """You are an expert AWS cloud architect and DevOps engineer.
Analyze service metrics and provide scaling recommendations.
Always respond in JSON format with these exact fields:
- action: string (one of: scale_up, scale_down, no_change)
- reason: string (why this action is recommended)
- recommended_instances: integer (suggested ECS task count)
- current_bottleneck: string (what resource is the bottleneck)
- cost_impact: string (estimated cost change)
- urgency: string (one of: immediate, within_hour, within_day, no_action)
- auto_scale_command: string (AWS CLI command to apply scaling)"""

    prompt = f"""Analyze these service metrics and recommend scaling action:

Service: {metrics.service_name}
Metrics (last {metrics.period_minutes} minutes):
- CPU Usage: {metrics.cpu_percent:.1f}%
- Memory Usage: {metrics.memory_percent:.1f}%
- Request Rate: {metrics.request_rate:.1f} req/sec
- Error Rate: {metrics.error_rate:.2f}%
- Avg Response Time: {metrics.avg_response_time_ms:.0f}ms

Respond ONLY with valid JSON."""

    ai_response = call_bedrock(prompt, system_prompt)

    try:
        recommendation = json.loads(ai_response)
    except json.JSONDecodeError:
        recommendation = {
            "action": "no_change",
            "reason": "Could not parse AI response",
            "recommended_instances": 2,
            "current_bottleneck": "unknown",
            "cost_impact": "unknown",
            "urgency": "no_action",
            "auto_scale_command": ""
        }

    record = {
        "id": f"SCALE-{int(time.time())}",
        "type": "scaling_advice",
        "service_name": metrics.service_name,
        "metrics": metrics.model_dump(),
        "recommendation": recommendation,
        "analyzed_at": datetime.utcnow().isoformat(),
        "duration_ms": round((time.time()-start)*1000)
    }
    analysis_db.append(record)

    # Auto-apply scaling if urgent and action is scale_up
    if recommendation.get("urgency") == "immediate" and recommendation.get("action") == "scale_up":
        logger.warning(json.dumps({
            "event": "auto_scaling_triggered",
            "service": metrics.service_name,
            "recommended_instances": recommendation.get("recommended_instances")
        }))

    return record

# ─────────────────────────────────────────
# AI: Anomaly Detector
# ─────────────────────────────────────────
@app.post("/api/ai/detect-anomaly")
def detect_anomaly(event: AnomalyEvent, background_tasks: BackgroundTasks):
    start = time.time()
    deviation = abs(event.current_value - event.baseline_value) / max(event.baseline_value, 1) * 100

    is_anomaly = deviation >= event.threshold_percent

    if is_anomaly:
        system_prompt = """You are a DevOps monitoring expert. Analyze metric anomalies and explain impact.
Respond in JSON with: impact (string), likely_cause (string), immediate_action (string), alert_level (critical/high/medium/low)"""

        prompt = f"""Anomaly detected in service metrics:
Service: {event.service_name}
Metric: {event.metric_name}
Current Value: {event.current_value}
Baseline (normal): {event.baseline_value}
Deviation: {deviation:.1f}%

What is the likely cause and impact? Respond ONLY with JSON."""

        ai_response = call_bedrock(prompt, system_prompt)
        try:
            ai_analysis = json.loads(ai_response)
        except:
            ai_analysis = {"impact": "High deviation detected", "likely_cause": "Unknown", "immediate_action": "Investigate logs", "alert_level": "high"}
    else:
        ai_analysis = {"impact": "None", "likely_cause": "Normal variation", "immediate_action": "No action needed", "alert_level": "low"}

    record = {
        "id": f"ANOMALY-{int(time.time())}",
        "type": "anomaly_detection",
        "service_name": event.service_name,
        "metric_name": event.metric_name,
        "current_value": event.current_value,
        "baseline_value": event.baseline_value,
        "deviation_percent": round(deviation, 2),
        "is_anomaly": is_anomaly,
        "ai_analysis": ai_analysis,
        "detected_at": datetime.utcnow().isoformat(),
        "duration_ms": round((time.time()-start)*1000)
    }
    analysis_db.append(record)

    if is_anomaly:
        background_tasks.add_task(notify_anomaly, event, ai_analysis, deviation)
        logger.warning(json.dumps({
            "event": "anomaly_detected", "service": event.service_name,
            "metric": event.metric_name, "deviation": f"{deviation:.1f}%"
        }))

    return record

# ─────────────────────────────────────────
# Dashboard API
# ─────────────────────────────────────────
@app.get("/api/ai/analyses")
def get_all_analyses(limit: int = 20, analysis_type: Optional[str] = None):
    results = analysis_db
    if analysis_type:
        results = [a for a in results if a["type"] == analysis_type]
    return {
        "analyses": list(reversed(results))[:limit],
        "total": len(results)
    }

@app.get("/api/ai/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    for a in analysis_db:
        if a["id"] == analysis_id:
            return a
    raise HTTPException(status_code=404, detail="Analysis not found")

@app.get("/api/ai/stats")
def get_stats():
    failures = [a for a in analysis_db if a["type"] == "pipeline_failure"]
    anomalies = [a for a in analysis_db if a["type"] == "anomaly_detection" and a["is_anomaly"]]
    scaling = [a for a in analysis_db if a["type"] == "scaling_advice"]
    return {
        "total_analyses": len(analysis_db),
        "pipeline_failures_analyzed": len(failures),
        "anomalies_detected": len(anomalies),
        "scaling_recommendations": len(scaling),
        "last_analyzed": analysis_db[-1]["analyzed_at"] if analysis_db else None
    }

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-engine", "model": BEDROCK_MODEL_ID, "timestamp": datetime.utcnow().isoformat()}

# ─────────────────────────────────────────
# Background notification tasks
# ─────────────────────────────────────────
async def notify_pipeline_failure(event: PipelineFailureEvent, analysis: dict):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{NOTIFICATION_SERVICE_URL}/api/notifications/pipeline-alert",
                params={
                    "service": event.service_name,
                    "status": f"FAILED at stage: {event.failed_stage}",
                    "ai_suggestion": analysis.get("fix_steps", ["Check logs"])[0]
                })
    except Exception as e:
        logger.warning(f"Could not send pipeline failure notification: {e}")

async def notify_anomaly(event: AnomalyEvent, analysis: dict, deviation: float):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{NOTIFICATION_SERVICE_URL}/api/notifications/pipeline-alert",
                params={
                    "service": event.service_name,
                    "status": f"ANOMALY: {event.metric_name} deviated {deviation:.1f}%",
                    "ai_suggestion": analysis.get("immediate_action", "Investigate immediately")
                })
    except Exception as e:
        logger.warning(f"Could not send anomaly notification: {e}")
