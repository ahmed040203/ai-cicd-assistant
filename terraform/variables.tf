variable "aws_region" {
  description = "AWS region"
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used as prefix for all resources"
  default     = "ai-cicd"
}

variable "environment" {
  description = "Environment name"
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "jenkins_instance_type" {
  description = "EC2 instance type for Jenkins"
  default     = "t3.medium"
}

variable "jenkins_key_name" {
  description = "EC2 key pair name for Jenkins SSH access"
  default     = "ai-cicd-key"
}

variable "db_instance_class" {
  description = "RDS instance class"
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "Database name"
  default     = "ai_cicd_db"
}

variable "db_username" {
  description = "Database master username"
  default     = "dbadmin"
}

variable "db_password" {
  description = "Database master password"
  sensitive   = true
  default     = "ChangeMe123!"
}

variable "services" {
  description = "List of microservice names"
  type        = list(string)
  default = [
    "user-service",
    "product-service",
    "order-service",
    "payment-service",
    "notification-service"
  ]
}
