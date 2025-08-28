# leaderboard_server.py
import asyncio
import websockets
import json
import boto3
import os
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Set

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

def init_dynamodb_table():
    # List all tables to check if leaderboard exists
    existing_tables = dynamodb.meta.client.list_tables()['TableNames']
    
    if 'leaderboard' in existing_tables:
        print("Deleting existing leaderboard table...")
        table = dynamodb.Table('leaderboard')
        table.delete()
        # Wait for table to be deleted
        waiter = table.meta.client.get_waiter('table_not_exists')
        waiter.wait(TableName='leaderboard')
        print("Deleted existing leaderboard table")
    
    # Create the table with the correct schema
    print("Creating new leaderboard table...")
    table = dynamodb.create_table(
        TableName='leaderboard',
        KeySchema=[{'AttributeName': 'player_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[
            {'AttributeName': 'player_id', 'AttributeType': 'S'},
            {'AttributeName': 'score', 'AttributeType': 'N'},
            {'AttributeName': 'leaderboard_id', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'score-index',
            'KeySchema': [
                {'AttributeName': 'leaderboard_id', 'KeyType': 'HASH'},
                {'AttributeName': 'score', 'KeyType': 'RANGE'},
            ],
            'Projection': {'ProjectionType': 'ALL'},
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        }],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    # Wait until the table exists
    table.meta.client.get_waiter('table_exists').wait(TableName='leaderboard')
    print("Successfully created leaderboard table with updated schema")
    return table

# Initialize DynamoDB table
table = init_dynamodb_table()

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

async def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch and return the current leaderboard from DynamoDB using GSI for better performance.
    Returns top 'limit' players sorted by score in descending order.
    """
    try:
        start_time = time.time()
        
        # Query the GSI to get top K scores in descending order
        response = table.query(
            IndexName='score-index',
            KeyConditionExpression='leaderboard_id = :lid AND #score > :zero',
            ExpressionAttributeNames={
                '#score': 'score'
            },
            ExpressionAttributeValues={
                 ':lid': 'default_leaderboard',
                 ':zero': 0
            },
            ScanIndexForward=False,  # Sort in descending order
            Limit=limit
        )
        items = response.get('Items', [])
        
        # Convert Decimal to float for JSON serialization
        items = convert_decimals(items)
        
        # Log performance metrics
        duration = (time.time() - start_time) * 1000  # Convert to milliseconds
        print(f"Leaderboard query completed in {duration:.2f}ms")
        
        return items
        
    except Exception as e:
        print(f"Error getting leaderboard: {e}")
        # Fallback to scan if GSI query fails
        try:
            print("Falling back to table scan...")
            response = table.scan()
            items = response.get('Items', [])
            return sorted(items, key=lambda x: x.get('score', 0), reverse=True)[:limit]
        except Exception as fallback_error:
            print(f"Fallback scan also failed: {fallback_error}")
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
                    player_id = data['player_id']
                    # Generate a consistent player ID by hashing the lowercase name
                    player_name = data.get('player_name', 'anonymous')
                    player_id = hashlib.md5(player_name.lower().encode('utf-8')).hexdigest()
                    
                    # Use update_item with ADD to atomically update the score
                    update_expression = 'ADD #score :score_val ' \
                                     'SET #timestamp = :timestamp, #player_name = :player_name, #leaderboard_id = :leaderboard_id'
                    
                    expression_attr_names = {
                        '#score': 'score',
                        '#timestamp': 'timestamp',
                        '#player_name': 'player_name',
                        '#leaderboard_id': 'leaderboard_id'
                    }
                    
                    # Default leaderboard ID if not specified
                    leaderboard_id = data.get('leaderboard_id', 'default_leaderboard')
                    
                    # Validate score
                    try:
                        score = int(data.get('score', 0))
                        if score <= 0:
                            raise ValueError("Score must be positive")
                    except (ValueError, TypeError) as e:
                        print(f"Invalid score from client: {data.get('score')}")
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Invalid score: must be a positive number'
                        }))
                        continue
                    
                    expression_attr_values = {
                        ':score_val': score,
                        ':timestamp': datetime.now(timezone.utc).isoformat(),
                        ':player_name': player_name,
                        ':leaderboard_id': leaderboard_id  # Store the original name for display
                    }
                    
                    print(f"Updating score for player: {player_name} (ID: {player_id})")
                    print(f"Update expression: {update_expression}")
                    
                    try:
                        response = table.update_item(
                            Key={'player_id': player_id},
                            UpdateExpression=update_expression,
                            ExpressionAttributeNames=expression_attr_names,
                            ExpressionAttributeValues=expression_attr_values,
                            ReturnValues='UPDATED_NEW'  # Return the updated values
                        )
                        print(f"DynamoDB update_item response: {response}")
                    except Exception as e:
                        print(f"Error in update_item: {str(e)}")
                        print(f"Error type: {type(e).__name__}")
                        print(f"Error args: {e.args}")
                        raise
                    
                    # Force an immediate leaderboard update
                    async with update_lock:
                        current_leaderboard = await get_leaderboard()
                    await broadcast_leaderboard()
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