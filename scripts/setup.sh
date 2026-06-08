#!/bin/bash
# ─────────────────────────────────────────
# AI CI/CD Assistant — Full Setup Script
# Run this once on your Linux machine
# ─────────────────────────────────────────

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AI CI/CD Assistant — Setup Script    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"

# ── Step 1: Check Prerequisites ──────────────────────────────
echo -e "\n${YELLOW}[1/6] Checking prerequisites...${NC}"

check_cmd() {
    if command -v $1 &> /dev/null; then
        echo -e "  ${GREEN}✓ $1 found${NC}"
    else
        echo -e "  ${RED}✗ $1 not found — please install it first${NC}"
        exit 1
    fi
}

check_cmd docker
check_cmd aws
check_cmd terraform
check_cmd python3
check_cmd git

echo -e "  ${GREEN}All prerequisites found!${NC}"

# ── Step 2: AWS Configuration Check ─────────────────────────
echo -e "\n${YELLOW}[2/6] Checking AWS configuration...${NC}"
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$AWS_ACCOUNT" ]; then
    echo -e "  ${RED}AWS not configured. Run: aws configure${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ AWS Account: $AWS_ACCOUNT${NC}"
echo -e "  ${GREEN}✓ Region: $(aws configure get region)${NC}"

export AWS_ACCOUNT_ID=$AWS_ACCOUNT
export AWS_REGION=$(aws configure get region || echo "us-east-1")

# ── Step 3: Create EC2 Key Pair ──────────────────────────────
echo -e "\n${YELLOW}[3/6] Setting up EC2 Key Pair...${NC}"
KEY_NAME="ai-cicd-key"
if [ ! -f ~/.ssh/${KEY_NAME}.pem ]; then
    echo "Creating key pair: $KEY_NAME"
    aws ec2 create-key-pair \
        --key-name $KEY_NAME \
        --query 'KeyMaterial' \
        --output text > ~/.ssh/${KEY_NAME}.pem
    chmod 400 ~/.ssh/${KEY_NAME}.pem
    echo -e "  ${GREEN}✓ Key pair created: ~/.ssh/${KEY_NAME}.pem${NC}"
else
    echo -e "  ${GREEN}✓ Key pair already exists${NC}"
fi

# ── Step 4: Terraform Init & Apply ───────────────────────────
echo -e "\n${YELLOW}[4/6] Running Terraform...${NC}"
cd terraform/

echo "Initializing Terraform..."
terraform init

echo "Planning infrastructure..."
terraform plan \
    -var="aws_region=$AWS_REGION" \
    -var="jenkins_key_name=$KEY_NAME" \
    -out=tfplan

echo ""
echo -e "${YELLOW}Review the plan above. Press ENTER to apply or Ctrl+C to cancel.${NC}"
read -r

terraform apply tfplan

# Save outputs
JENKINS_IP=$(terraform output -raw jenkins_public_ip)
ALB_DNS=$(terraform output -raw alb_dns_name)
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)

echo -e "\n${GREEN}✓ Infrastructure created!${NC}"
echo -e "  Jenkins IP:   $JENKINS_IP"
echo -e "  ALB DNS:      $ALB_DNS"
echo -e "  ECS Cluster:  $ECS_CLUSTER"

# Save to .env file
cd ..
cat > .env << EOF
AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID
AWS_REGION=$AWS_REGION
JENKINS_IP=$JENKINS_IP
JENKINS_URL=http://$JENKINS_IP:8080
ALB_DNS=$ALB_DNS
RDS_ENDPOINT=$RDS_ENDPOINT
ECS_CLUSTER=$ECS_CLUSTER
EOF
echo -e "  ${GREEN}✓ Saved to .env${NC}"

# ── Step 5: Build & Push Docker Images ───────────────────────
echo -e "\n${YELLOW}[5/6] Building and pushing Docker images...${NC}"

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Authenticate with ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REGISTRY

for service in user-service product-service order-service payment-service notification-service; do
    echo -e "\n  Building ${service}..."
    docker build -t ai-cicd/${service}:latest ./services/${service}/
    docker tag ai-cicd/${service}:latest ${ECR_REGISTRY}/ai-cicd/${service}:latest
    docker push ${ECR_REGISTRY}/ai-cicd/${service}:latest
    echo -e "  ${GREEN}✓ ${service} pushed${NC}"
done

echo -e "\n  Building ai-engine..."
docker build -t ai-cicd/ai-engine:latest ./ai-engine/
docker tag ai-cicd/ai-engine:latest ${ECR_REGISTRY}/ai-cicd/ai-engine:latest
docker push ${ECR_REGISTRY}/ai-cicd/ai-engine:latest
echo -e "  ${GREEN}✓ ai-engine pushed${NC}"

# ── Step 6: Configure Jenkins ────────────────────────────────
echo -e "\n${YELLOW}[6/6] Jenkins setup instructions...${NC}"
echo ""
echo -e "Jenkins is running at: ${GREEN}http://$JENKINS_IP:8080${NC}"
echo ""
echo "To get Jenkins initial password:"
echo -e "  ${BLUE}ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@$JENKINS_IP${NC}"
echo -e "  ${BLUE}sudo cat /var/lib/jenkins/secrets/initialAdminPassword${NC}"
echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Open Jenkins at http://$JENKINS_IP:8080"
echo "  2. Install suggested plugins"
echo "  3. Add AWS credentials in Jenkins"
echo "  4. Create pipelines for each service"
echo "  5. Test locally: docker compose up"
