from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging, time, os, random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="AI CI/CD Assistant Engine", version="1.0.0")

analysis_db: List[dict] = []

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

def mock_ai_analysis(error_logs: str, failed_stage: str) -> dict:
    if "not found" in error_logs or "command not found" in error_logs:
        return {
            "root_cause": f"Missing dependency or tool not installed in the CI/CD environment during {failed_stage} stage.",
            "severity": "high",
            "fix_steps": [
                "Install the missing tool in the Jenkins agent",
                "Add tool installation step to Jenkinsfile",
                "Verify PATH environment variable in pipeline"
            ],
            "code_fix": "sudo apt-get install -y awscli",
            "prevention": "Use Docker-based agents with pre-installed tools",
            "estimated_fix_time": "15 minutes"
        }
    elif "permission" in error_logs.lower() or "access denied" in error_logs.lower():
        return {
            "root_cause": "Insufficient IAM permissions for the operation.",
            "severity": "critical",
            "fix_steps": [
                "Review IAM role attached to Jenkins EC2",
                "Add required permissions to the IAM policy",
                "Test with aws sts get-caller-identity"
            ],
            "code_fix": "aws iam attach-role-policy --role-name jenkins-role --policy-arn arn:aws:iam::aws:policy/AmazonECRFullAccess",
            "prevention": "Use least-privilege IAM policies with regular audits",
            "estimated_fix_time": "30 minutes"
        }
    elif "timeout" in error_logs.lower() or "connection" in error_logs.lower():
        return {
            "root_cause": "Network connectivity issue or service timeout during pipeline execution.",
            "severity": "medium",
            "fix_steps": [
                "Check VPC security group rules",
                "Verify NAT Gateway is operational",
                "Increase timeout values in pipeline configuration"
            ],
            "code_fix": "aws ec2 describe-security-groups --group-ids <sg-id>",
            "prevention": "Implement retry logic and circuit breakers",
            "estimated_fix_time": "20 minutes"
        }
    else:
        return {
            "root_cause": f"Pipeline failure detected in {failed_stage} stage. Error requires investigation.",
            "severity": "high",
            "fix_steps": [
                "Review complete error logs",
                "Check service dependencies",
                "Verify Docker image builds correctly",
                "Test pipeline stages individually"
            ],
            "code_fix": "docker build -t test . && docker run --rm test python -m pytest",
            "prevention": "Add comprehensive logging and monitoring to each pipeline stage",
            "estimated_fix_time": "45 minutes"
        }

@app.post("/api/ai/analyze-failure")
def analyze_pipeline_failure(event: PipelineFailureEvent, background_tasks: BackgroundTasks):
    start = time.time()
    analysis = mock_ai_analysis(event.error_logs, event.failed_stage)
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
        "duration_ms": round((time.time()-start)*1000),
        "ai_provider": "mock-ai-demo"
    }
    analysis_db.append(record)
    return record

@app.post("/api/ai/scaling-advice")
def get_scaling_advice(metrics: MetricsEvent):
    start = time.time()
    if metrics.cpu_percent > 80:
        action, instances, urgency = "scale_up", 4, "immediate"
    elif metrics.cpu_percent < 20 and metrics.memory_percent < 20:
        action, instances, urgency = "scale_down", 1, "within_hour"
    else:
        action, instances, urgency = "no_change", 2, "no_action"
    recommendation = {
        "action": action,
        "reason": f"CPU at {metrics.cpu_percent}%, Memory at {metrics.memory_percent}%",
        "recommended_instances": instances,
        "current_bottleneck": "CPU" if metrics.cpu_percent > 80 else "None",
        "cost_impact": "+$50/month" if action == "scale_up" else "-$25/month" if action == "scale_down" else "No change",
        "urgency": urgency,
        "auto_scale_command": f"aws ecs update-service --cluster ai-cicd-cluster --service {metrics.service_name} --desired-count {instances}"
    }
    record = {
        "id": f"SCALE-{int(time.time())}",
        "type": "scaling_advice",
        "service_name": metrics.service_name,
        "metrics": metrics.model_dump(),
        "recommendation": recommendation,
        "analyzed_at": datetime.utcnow().isoformat(),
        "duration_ms": round((time.time()-start)*1000),
        "ai_provider": "mock-ai-demo"
    }
    analysis_db.append(record)
    return record

@app.post("/api/ai/detect-anomaly")
def detect_anomaly(event: AnomalyEvent, background_tasks: BackgroundTasks):
    start = time.time()
    deviation = abs(event.current_value - event.baseline_value) / max(event.baseline_value, 1) * 100
    is_anomaly = deviation >= event.threshold_percent
    ai_analysis = {
        "impact": "Service degradation possible" if is_anomaly else "None",
        "likely_cause": "Traffic spike or memory leak" if is_anomaly else "Normal variation",
        "immediate_action": "Scale up and investigate logs" if is_anomaly else "No action needed",
        "alert_level": "high" if is_anomaly else "low"
    }
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
        "duration_ms": round((time.time()-start)*1000),
        "ai_provider": "mock-ai-demo"
    }
    analysis_db.append(record)
    return record

@app.get("/api/ai/analyses")
def get_all_analyses(limit: int = 20, analysis_type: Optional[str] = None):
    results = analysis_db
    if analysis_type:
        results = [a for a in results if a["type"] == analysis_type]
    return {"analyses": list(reversed(results))[:limit], "total": len(results)}

@app.get("/api/ai/stats")
def get_stats():
    failures = [a for a in analysis_db if a["type"] == "pipeline_failure"]
    anomalies = [a for a in analysis_db if a["type"] == "anomaly_detection" and a.get("is_anomaly")]
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
    return {"status": "healthy", "service": "ai-engine", "model": "mock-ai-demo", "timestamp": datetime.utcnow().isoformat()}
