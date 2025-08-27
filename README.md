# Leaderboard Demo

A real-time leaderboard application using WebSockets, DynamoDB, and LocalStack.

## Architecture

```
┌─────────────────┐     WebSocket     ┌──────────────────┐
│                 │  ┌─────────────┐  │                  │
│    Frontend     │◄──┤ Real-time  ├──│  WebSocket      │
│  (React/Vite)   │──►┤  Updates   │  │  Server         │
│                 │   └────────────┘  │                  │
└────────┬────────┘        ▲          └────────┬─────────┘
         │                 │                   │
         │ HTTP            │                   │
         │ API             │                   │ CRUD Operations
         │                 │                   │
         ▼                 │                   ▼
┌─────────────────┐        │          ┌──────────────────┐
│                 │        │          │                  │
│  LocalStack     │        └──────────┤    DynamoDB      │
│  (AWS Services) ├───────────────────►    (Database)    │
│                 │                   │                  │
└─────────────────┘                   └──────────────────┘
```

### Components

1. **Frontend**
   - React application built with Vite
   - Connects to WebSocket server for real-time updates
   - Sends/receives leaderboard data via WebSockets

2. **WebSocket Server**
   - Handles real-time communication with clients
   - Processes leaderboard updates
   - Manages WebSocket connections

3. **DynamoDB**
   - Stores leaderboard data
   - Provides fast read/write operations for real-time updates

4. **LocalStack**
   - Provides local AWS services for development
   - Includes DynamoDB, API Gateway, and other AWS services

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Node.js 16+ (for frontend development)
- Terraform (for infrastructure if needed)

## Development Setup (Right now this is using Nginx, but normally would use Vite)

1. Start the backend services:
   ```bash
   docker compose up -d localstack websocket-server
   ```

2. Start the frontend development server:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`

3. Access the WebSocket server at `ws://localhost:8765`

## Production Setup 

1. Build and start all services:
   ```bash
   docker compose --profile production up --build -d
   ```
   This will:
   - Build the frontend with production optimizations
   - Serve it through Nginx on port 80
   - Start the WebSocket server
   - Initialize LocalStack for local AWS services

2. Access the application at `http://localhost`

## Project Structure

- `frontend/` - React application (Vite)
- `backend/` - WebSocket server and business logic
- `infrastructure/` - Terraform configurations (if applicable)
- `docker-compose.yml` - Development and production service definitions

## Environment Variables

### Frontend
- `VITE_WS_URL` - WebSocket server URL (default: `ws://localhost/ws` in production)

### Backend
- `AWS_ENDPOINT_URL` - LocalStack endpoint (default: `http://localhost:4566`)
- `AWS_ACCESS_KEY_ID` - AWS access key (default: `test`)
- `AWS_SECRET_ACCESS_KEY` - AWS secret key (default: `test`)
- `AWS_DEFAULT_REGION` - AWS region (default: `us-east-1`)