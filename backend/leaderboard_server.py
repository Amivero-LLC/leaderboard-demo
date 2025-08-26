# leaderboard_server.py
import asyncio
import websockets
import json
import boto3
from datetime import datetime, timezone

# Initialize DynamoDB client (LocalStack)
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url='http://localhost:4566',
    region_name='us-east-1',
    aws_access_key_id='test',
    aws_secret_access_key='test'
)

# Create table if it doesn't exist
try:
    table = dynamodb.create_table(
        TableName='Leaderboard',
        KeySchema=[{'AttributeName': 'player_id', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'player_id', 'AttributeType': 'S'}],
        BillingMode='PAY_PER_REQUEST'
    )
    table.meta.client.get_waiter('table_exists').wait(TableName='Leaderboard')
except dynamodb.meta.client.exceptions.ResourceInUseException:
    table = dynamodb.Table('Leaderboard')

# Store WebSocket connections
connected = set()

def convert_decimals(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif str(type(obj)) == "<class 'decimal.Decimal'>":
        return float(obj)
    return obj

async def update_leaderboard():
    """Broadcast current leaderboard to all connected clients"""
    response = table.scan()
    leaderboard = sorted(
        response['Items'],
        key=lambda x: x.get('score', 0),
        reverse=True
    )[:10]  # Top 10 players
    
    # Convert Decimal to float for JSON serialization
    leaderboard = convert_decimals(leaderboard)
    
    message = json.dumps({
        'type': 'leaderboard_update',
        'data': leaderboard,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    # Send to all connected clients
    for connection in connected:
        try:
            await connection.send(message)
        except:
            # Remove dead connections
            connected.remove(connection)

async def handle_connection(websocket, path):
    connected.add(websocket)
    client_id = id(websocket)
    print(f"Client {client_id} connected")
    
    try:
        # Send current leaderboard on new connection
        print(f"Sending initial leaderboard to client {client_id}")
        await update_leaderboard()
        
        async for message in websocket:
            print(f"Received from client {client_id}: {message}")
            try:
                data = json.loads(message)
                action = data.get('action')
                
                if action == 'submit_score':
                    print(f"Processing submit_score from client {client_id}")
                    # Update player score in DynamoDB
                    table.put_item(Item={
                        'player_id': data['player_id'],
                        'player_name': data['player_name'],
                        'score': int(data['score']),
                        'last_updated': datetime.now(timezone.utc).isoformat()
                    })
                    # Broadcast updated leaderboard
                    await update_leaderboard()
                else:
                    print(f"Unknown action from client {client_id}: {action}")
                    
            except json.JSONDecodeError as e:
                print(f"Error decoding message from client {client_id}: {e}")
            except Exception as e:
                print(f"Error processing message from client {client_id}: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"Client {client_id} disconnected unexpectedly")
    except Exception as e:
        print(f"Error with client {client_id}: {e}")
    finally:
        if websocket in connected:
            connected.remove(websocket)
        print(f"Client {client_id} disconnected")

# Start WebSocket server
start_server = websockets.serve(handle_connection, "0.0.0.0", 8765)

print("WebSocket server started on ws://localhost:8765")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()