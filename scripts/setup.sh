#!/bin/bash
set -e

# Start LocalStack in detached mode
echo "Starting LocalStack..."
docker compose up -d --remove-orphans

# Install dependencies
echo "Installing Python dependencies..."
cd backend
pipi -r requirements.txt -t .

# Package Lambda function
echo "Packaging Lambda function..."
zip -r webhook.zip .

# Initialize and apply Terraform
echo "Initializing Terraform..."
cd ../infrastructure
terraform init

echo "Applying Terraform configuration..."
terraform apply -auto-approve

echo -e "\nSetup complete! WebSocket URL:"
terraform output -raw websocket_url
