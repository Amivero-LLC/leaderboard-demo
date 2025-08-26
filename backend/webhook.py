import json
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb', 
                         endpoint_url='http://host.docker.internal:4566',
                         region_name='us-east-1',
                         aws_access_key_id='test',
                         aws_secret_access_key='test')
table = dynamodb.Table('Leaderboard')

def handler(event, context):
    try:
        # Parse the request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Handle different actions
        action = body.get('action', '')
        
        if action == 'submit_score':
            # Submit a new score
            item = {
                'player_id': body['player_id'],
                'score': int(body['score']),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Add optional fields if they exist
            if 'player_name' in body:
                item['player_name'] = body['player_name']
            
            # Save to DynamoDB
            table.put_item(Item=item)
            
            # Get updated leaderboard
            return get_leaderboard()
            
        elif action == 'get_leaderboard':
            # Just return the leaderboard
            return get_leaderboard()
            
        else:
            # Default action if no specific action is provided
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid action. Use "submit_score" or "get_leaderboard"'})
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_leaderboard():
    # Get all items and sort by score
    response = table.scan()
    leaderboard = sorted(
        response.get('Items', []),
        key=lambda x: x.get('score', 0),
        reverse=True
    )[:10]  # Get top 10 scores
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps({
            'status': 'success',
            'data': leaderboard
        })
    }