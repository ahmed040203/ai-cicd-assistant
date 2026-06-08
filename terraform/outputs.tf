output "jenkins_public_ip" {
  description = "Jenkins EC2 public IP"
  value       = aws_eip.jenkins.public_ip
}

output "jenkins_url" {
  description = "Jenkins URL"
  value       = "http://${aws_eip.jenkins.public_ip}:8080"
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "ecr_repository_urls" {
  description = "ECR repository URLs for each service"
  value       = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "sns_pipeline_alerts_arn" {
  description = "SNS topic ARN for pipeline alerts"
  value       = aws_sns_topic.pipeline_alerts.arn
}

output "sqs_log_analysis_url" {
  description = "SQS queue URL for log analysis"
  value       = aws_sqs_queue.log_analysis.url
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
