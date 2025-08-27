# leaderboard_server.py
import asyncio
import websockets
import json
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Set, Optional

# Initialize DynamoDB client (LocalStack)
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url=os.getenv('AWS_ENDPOINT_URL', 'http://localhost:4566'),
    region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'test'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
)

# Store connected WebSocket clients
connected: Set[Any] = set()

# Initialize DynamoDB table
try:
    table = dynamodb.create_table(
        TableName='leaderboard',
        KeySchema=[
            {
                'AttributeName': 'player_id',
                'KeyType': 'HASH'  # Partition key
            },
            {
                'AttributeName': 'score',
                'KeyType': 'RANGE'  # Sort key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'player_id',
                'AttributeType': 'S'  # String
            },
            {
                'AttributeName': 'score',
                'AttributeType': 'N'  # Number
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    # Wait until the table exists
    table.meta.client.get_waiter('table_exists').wait(TableName='leaderboard')
    print("Created DynamoDB table 'leaderboard'")
except Exception as e:
    if 'ResourceInUseException' in str(e):
        table = dynamodb.Table('leaderboard')
        print("Using existing DynamoDB table 'leaderboard'")
    else:
        print(f"Error creating DynamoDB table: {e}")
        raise

# Cache for the current leaderboard state
current_leaderboard: List[Dict[str, Any]] = []
last_update_time: float = 0
update_lock = asyncio.Lock()

# Convert Decimal objects to float for JSON serialization
def convert_decimals(obj):
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif str(type(obj)) == "<class 'decimal.Decimal'>":
        return float(obj)
    return obj

async def get_leaderboard() -> List[Dict[str, Any]]:
    """Fetch and return the current leaderboard from DynamoDB"""
    try:
        response = table.scan()
        leaderboard = sorted(
            response['Items'],
            key=lambda x: x.get('score', 0),
            reverse=True
        )[:10]  # Top 10 players
        return convert_decimals(leaderboard)
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        return []

async def broadcast_leaderboard():
    """Broadcast the current leaderboard to all connected clients"""
    if not connected:
        return
        
    try:
        message = json.dumps({
            'type': 'leaderboard_update',
            'data': current_leaderboard,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Send to all connected clients
        dead_connections = []
        for connection in connected:
            try:
                await connection.send(message)
            except:
                # Mark dead connections for removal
                dead_connections.append(connection)
        
        # Remove dead connections
        for connection in dead_connections:
            if connection in connected:
                connected.remove(connection)
                
    except Exception as e:
        print(f"Error broadcasting leaderboard: {e}")

async def update_leaderboard():
    """Periodically update the leaderboard and broadcast changes"""
    global current_leaderboard
    
    while True:
        try:
            # Only update if we have connected clients
            if connected:
                # Get fresh leaderboard data
                new_leaderboard = await get_leaderboard()
                
                # Only update and broadcast if the leaderboard has changed
                if new_leaderboard != current_leaderboard:
                    async with update_lock:
                        current_leaderboard = new_leaderboard
                    await broadcast_leaderboard()
            
            # Wait before next update (1 second)
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error in update_leaderboard: {e}")
            # Wait a bit before retrying on error
            await asyncio.sleep(5)

# Flag to track if the update task is running
update_task = None

async def handle_connection(websocket, path):
    global update_task, current_leaderboard
    client_id = id(websocket)
    print(f"Client {client_id} connected")
    
    try:
        # Start the update task if it's not already running
        if update_task is None or update_task.done():
            # Get initial leaderboard data
            current_leaderboard = await get_leaderboard()
            update_task = asyncio.create_task(update_leaderboard())
        
        # Add client to connected set
        connected.add(websocket)
        
        # Send current leaderboard to this client
        try:
            await websocket.send(json.dumps({
                'type': 'leaderboard_update',
                'data': current_leaderboard,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }))
        except Exception as e:
            print(f"Error sending initial leaderboard: {e}")
        
        # Keep the connection alive and handle incoming messages
        async for message in websocket:
            print(f"Received from client {client_id}: {message}")
            try:
                data = json.loads(message)
                action = data.get('action')
                
                if action == 'submit_score':
                    print(f"Processing submit_score from client {client_id}")
                    # Update player score in DynamoDB
                    try:
                        table.put_item(Item={
                            'player_id': data['player_id'],
                            'score': data['score'],
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            **({'player_name': data['player_name']} if 'player_name' in data else {})
                        })
                        # Force an immediate leaderboard update
                        async with update_lock:
                            current_leaderboard = await get_leaderboard()
                        await broadcast_leaderboard()
                    except Exception as e:
                        print(f"Error submitting score: {e}")
                else:
                    print(f"Unknown action from client {client_id}: {action}")
                    
            except json.JSONDecodeError as e:
                print(f"Error decoding message from client {client_id}: {e}")
            except Exception as e:
                print(f"Error processing message from client {client_id}: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"Error in client {client_id} connection: {e}")
    finally:
        connected.discard(websocket)
        print(f"Client {client_id} removed from connections")
        
        # If no more clients, cancel the update task
        if not connected and update_task and not update_task.done():
            update_task.cancel()
            try:
                await update_task
            except asyncio.CancelledError:
                pass
            update_task = None
            print("Stopped leaderboard updates - no active clients")

# Start WebSocket server
start_server = websockets.serve(handle_connection, "0.0.0.0", 8765)

print("WebSocket server started on ws://localhost:8765")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()