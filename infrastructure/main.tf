provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  skip_region_validation      = true

  endpoints {
    dynamodb   = "http://localhost:4566"
    apigateway = "http://localhost:4566"
    lambda     = "http://localhost:4566"
    iam        = "http://localhost:4566"
    cloudwatch = "http://localhost:4566"
    sts        = "http://localhost:4566"
  }

  # Workaround for LocalStack IAM
  default_tags {
    tags = {
      Environment = "local"
      Terraform   = "true"
    }
  }
}

# DynamoDB Table
resource "aws_dynamodb_table" "leaderboard" {
  name         = "Leaderboard"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "player_id"

  attribute {
    name = "player_id"
    type = "S"
  }

  tags = {
    Environment = "local"
  }
}

# API Gateway (REST API)
resource "aws_api_gateway_rest_api" "leaderboard" {
  name        = "leaderboard-api"
  description = "Leaderboard API"
}

# Webhook Server IAM Role
resource "aws_iam_role" "webhook_role" {
  name = "webhook-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# Webhook Lambda
resource "aws_lambda_function" "webhook" {
  filename      = "../backend/webhook.zip"
  function_name = "leaderboard-webhook"
  role          = aws_iam_role.webhook_role.arn
  handler       = "webhook.handler"
  runtime       = "python3.11"
  timeout       = 30

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.leaderboard.name
    }
  }
}

# API Gateway Resource
resource "aws_api_gateway_resource" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.leaderboard.id
  parent_id   = aws_api_gateway_rest_api.leaderboard.root_resource_id
  path_part   = "webhook"
}

# API Gateway Method
resource "aws_api_gateway_method" "webhook" {
  rest_api_id   = aws_api_gateway_rest_api.leaderboard.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway Integration
resource "aws_api_gateway_integration" "webhook" {
  rest_api_id             = aws_api_gateway_rest_api.leaderboard.id
  resource_id             = aws_api_gateway_resource.webhook.id
  http_method             = aws_api_gateway_method.webhook.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.webhook.invoke_arn
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "dev" {
  depends_on = [aws_api_gateway_integration.webhook]
  rest_api_id = aws_api_gateway_rest_api.leaderboard.id
  
  # Workaround for LocalStack
  variables = {
    deployed_at = timestamp()
  }
  
  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway Stage
resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.dev.id
  rest_api_id   = aws_api_gateway_rest_api.leaderboard.id
  stage_name    = "dev"
}

output "api_url" {
  value = "http://localhost:4566/restapis/${aws_api_gateway_rest_api.leaderboard.id}/dev/_user_request_/webhook"
}