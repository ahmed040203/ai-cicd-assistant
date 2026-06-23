# AI-Powered CI/CD Assistant

## Overview

AI-Powered CI/CD Assistant that manages an e-commerce microservices application on AWS. The system uses AI (AWS Bedrock / Claude) to automatically:
- **Detect and explain pipeline failures** with root cause analysis
- **Suggest fixes** with code-level recommendations
- **Advise on scaling** based on real-time metrics
- **Detect anomalies** before they become incidents

---

## Architecture

```
Developer → GitHub → Jenkins Pipeline (EC2)
                          │
          ┌───────────────┼───────────────┐
          │               │               │
       Build            Test           Deploy
          │               │               │
     Docker Build    pytest tests    Push ECR → ECS
          │
     [On Failure] → AI Engine (Bedrock)
                          │
                    ┌─────┴─────┐
                    │  Analyze  │
                    │  Fix      │
                    │  Scale    │
                    │  Alert    │
                    └─────┬─────┘
                          │
                    Dashboard + Slack
```

## Project Structure

```
ai-cicd-assistant/
├── terraform/              # AWS Infrastructure as Code
│   ├── main.tf             # VPC, subnets, IGW, NAT
│   ├── security_groups.tf  # SGs for Jenkins, ECS, ALB, RDS
│   ├── ec2_jenkins.tf      # Jenkins EC2 with user_data
│   ├── services.tf         # RDS, ECR, ECS, ALB, SNS, SQS
│   ├── variables.tf
│   └── outputs.tf
├── services/               # E-Commerce Microservices
│   ├── user-service/       # FastAPI: Register, Login, JWT
│   ├── product-service/    # FastAPI: Products CRUD, Search
│   ├── order-service/      # FastAPI: Orders, Cart
│   ├── payment-service/    # FastAPI: Mock Stripe payments
│   └── notification-service/ # FastAPI: Email/SMS via SQS
├── ai-engine/              # AI Analysis Engine
│   └── main.py             # Bedrock integration: analyze, scale, detect
├── dashboard/              # React + FastAPI dashboard
│   ├── frontend/           # React app
│   └── backend/            # FastAPI aggregation API
├── jenkins/
│   └── Jenkinsfile.template # Shared pipeline for all services
├── scripts/
│   ├── setup.sh            # One-command setup
│   └── init_db.sql         # Database schema
└── docker-compose.yml      # Local development
```

## Quick Start

### Local Development

```bash
# Clone repo
git clone https://github.com/YOUR_USERNAME/ai-cicd-assistant.git
cd ai-cicd-assistant

# Start all services locally
docker compose up --build

# Services available at:
# user-service:         http://localhost:8001
# product-service:      http://localhost:8002
# order-service:        http://localhost:8003
# payment-service:      http://localhost:8004
# notification-service: http://localhost:8005
# ai-engine:            http://localhost:8010
```

### AWS Deployment

```bash
# Prerequisites: AWS CLI configured, Terraform installed
chmod +x scripts/setup.sh
./scripts/setup.sh
```

## E-Commerce API Reference

### User Service (port 8001)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/users/register | Register new user |
| POST | /api/users/login | Login, get JWT token |
| GET | /api/users/me | Get current user |

### Product Service (port 8002)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/products | List products (filterable) |
| GET | /api/products/{id} | Get single product |
| POST | /api/products | Create product |
| POST | /api/products/{id}/reserve | Reserve stock |
| GET | /api/products/search/{q} | Search products |

### Order Service (port 8003)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/orders | Create order |
| GET | /api/orders/{id} | Get order |
| GET | /api/orders/user/{uid} | Get user orders |
| PATCH | /api/orders/{id}/status | Update status |

### Payment Service (port 8004)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/payments/charge | Process payment |
| GET | /api/payments/{id} | Get payment |
| POST | /api/payments/{id}/refund | Refund payment |

## AI Engine API

### Analyze Pipeline Failure
```bash
curl -X POST http://localhost:8010/api/ai/analyze-failure \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_name": "user-service-pipeline",
    "service_name": "user-service",
    "failed_stage": "Test",
    "error_logs": "FAILED test_login_success - ConnectionRefusedError: [Errno 111] Connection refused",
    "build_number": 42,
    "branch": "main"
  }'
```

### Get Scaling Advice
```bash
curl -X POST http://localhost:8010/api/ai/scaling-advice \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "product-service",
    "cpu_percent": 87.5,
    "memory_percent": 72.0,
    "request_rate": 450.0,
    "error_rate": 2.3,
    "avg_response_time_ms": 850
  }'
```

### Detect Anomaly
```bash
curl -X POST http://localhost:8010/api/ai/detect-anomaly \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-service",
    "metric_name": "error_rate",
    "current_value": 15.2,
    "baseline_value": 0.5
  }'
```

## Running Tests

```bash
# Run tests for all services
for service in user-service product-service; do
    cd services/$service
    pip install -r requirements.txt
    pytest test_main.py -v
    cd ../..
done
```

## AWS Services Used

| Service | Purpose |
|---------|---------|
| EC2 (t3.medium) | Jenkins CI/CD server |
| ECS Fargate | Run microservice containers |
| ECR | Docker image registry |
| RDS PostgreSQL | Application databases |
| CloudWatch | Logs and metrics |
| Bedrock (Claude) | AI analysis engine |
| ALB | Load balancer |
| SNS + SQS | Event messaging |
| VPC | Network isolation |

## Demo Scenarios

### Scenario 1: Pipeline Failure + AI Fix
1. Introduce a bug in user-service (break a test)
2. Push to GitHub → Jenkins triggers
3. Test stage fails → AI Engine analyzes logs
4. Dashboard shows: root cause + fix steps
5. Slack alert sent with AI suggestion

### Scenario 2: High Traffic + AI Scaling
1. Run load test: `locust -f tests/locust_test.py`
2. CPU spikes on product-service
3. AI Engine detects: "scale_up" recommendation
4. Dashboard shows scaling advice
5. Apply: ECS updates desired count

### Scenario 3: Anomaly Detection
1. Set payment-service failure rate to 30%
2. AI detects error rate anomaly vs baseline
3. Alert sent before SLA breach

## Team

- Member 1: Terraform + AWS Infrastructure
- Member 2: Jenkins Pipelines + Docker
- Member 3: AI Engine + Bedrock Integration

## Technologies

`Python` `FastAPI` `Docker` `Jenkins` `AWS ECS` `AWS Bedrock` `Terraform` `PostgreSQL` `React` `CloudWatch` `Grafana`
