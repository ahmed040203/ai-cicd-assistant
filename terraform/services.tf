# ─────────────────────────────────────────
# RDS — PostgreSQL
# ─────────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

resource "aws_db_instance" "main" {
  identifier        = "${var.project_name}-postgres"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = var.db_instance_class
  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  skip_final_snapshot     = true
  deletion_protection     = false
  multi_az                = false

  tags = {
    Name = "${var.project_name}-postgres"
  }
}

# ─────────────────────────────────────────
# ECR — One repository per service
# ─────────────────────────────────────────
resource "aws_ecr_repository" "services" {
  for_each = toset(var.services)

  name                 = "${var.project_name}/${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name    = "${var.project_name}-${each.value}"
    Service = each.value
  }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# ─────────────────────────────────────────
# ECS Cluster
# ─────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ─────────────────────────────────────────
# IAM Role for ECS Task Execution
# ─────────────────────────────────────────
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "ecs_cloudwatch" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# ─────────────────────────────────────────
# CloudWatch Log Groups (one per service)
# ─────────────────────────────────────────
resource "aws_cloudwatch_log_group" "services" {
  for_each = toset(var.services)

  name              = "/ecs/${var.project_name}/${each.value}"
  retention_in_days = 14

  tags = {
    Service = each.value
  }
}

resource "aws_cloudwatch_log_group" "jenkins" {
  name              = "/ec2/${var.project_name}/jenkins"
  retention_in_days = 14
}

# ─────────────────────────────────────────
# ALB — Application Load Balancer
# ─────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "AI CI/CD Assistant - Service Running"
      status_code  = "200"
    }
  }
}

# Target groups per service
resource "aws_lb_target_group" "services" {
  for_each = toset(var.services)

  name        = "${var.project_name}-${substr(each.value, 0, 20)}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Service = each.value
  }
}

# ─────────────────────────────────────────
# SNS Topics
# ─────────────────────────────────────────
resource "aws_sns_topic" "pipeline_alerts" {
  name = "${var.project_name}-pipeline-alerts"
}

resource "aws_sns_topic" "ai_insights" {
  name = "${var.project_name}-ai-insights"
}

resource "aws_sns_topic" "scaling_events" {
  name = "${var.project_name}-scaling-events"
}

# ─────────────────────────────────────────
# SQS Queues
# ─────────────────────────────────────────
resource "aws_sqs_queue" "log_analysis" {
  name                      = "${var.project_name}-log-analysis"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 86400
  visibility_timeout_seconds = 300

  tags = {
    Name = "${var.project_name}-log-analysis"
  }
}

resource "aws_sqs_queue" "notifications" {
  name                      = "${var.project_name}-notifications"
  delay_seconds             = 0
  message_retention_seconds = 86400
  visibility_timeout_seconds = 60

  tags = {
    Name = "${var.project_name}-notifications"
  }
}

# SNS → SQS subscription
resource "aws_sns_topic_subscription" "pipeline_to_sqs" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.log_analysis.arn
}

resource "aws_sqs_queue_policy" "log_analysis" {
  queue_url = aws_sqs_queue.log_analysis.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.log_analysis.arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_sns_topic.pipeline_alerts.arn
        }
      }
    }]
  })
}
