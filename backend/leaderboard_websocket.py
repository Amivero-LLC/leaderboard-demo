import asyncio
import json
from typing import Any, Dict, List, Set, Tuple
import heapq
from fastapi import WebSocket

class InMemoryLeaderboard:
    def __init__(self, top_k: int = 10):
        self.top_k = top_k
        self.scores: Dict[str, int] = {}  # user_id -> score
        self.heap: List[Tuple[int, str]] = []  # min-heap of (score, user_id)
        self.subscribers: Set[WebSocket] = set()

    async def add_subscriber(self, websocket: WebSocket):
        self.subscribers.add(websocket)
        await self._send_updates()

    def remove_subscriber(self, websocket: WebSocket):
        self.subscribers.discard(websocket)

    async def update_score(self, user_id: str, points: int):
        # Update the score
        self.scores[user_id] = self.scores.get(user_id, 0) + points
        current_score = self.scores[user_id]
        
        # Update the heap
        for i, (score, uid) in enumerate(self.heap):
            if uid == user_id:
                self.heap[i] = (current_score, user_id)
                heapq.heapify(self.heap)
                break
        else:
            if len(self.heap) < self.top_k:
                heapq.heappush(self.heap, (current_score, user_id))
            elif current_score > self.heap[0][0]:
                heapq.heappop(self.heap)
                heapq.heappush(self.heap, (current_score, user_id))
        
        await self._send_updates()

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get top K scores in descending order"""
        sorted_scores = sorted(self.heap, key=lambda x: (-x[0], x[1]))
        return [{"user_id": uid, "score": score} for score, uid in sorted_scores]

    async def _send_updates(self):
        """Send current leaderboard to all subscribers"""
        leaderboard = self.get_leaderboard()
        message = json.dumps({"type": "leaderboard_update", "data": leaderboard})
        # Create a list copy of subscribers to avoid modification during iteration
        for websocket in list(self.subscribers):
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"Error sending message to WebSocket: {e}")
                self.remove_subscriber(websocket)

# Global instance
leaderboard = InMemoryLeaderboard(top_k=10)

# FastAPI app setup
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("New WebSocket connection established")
    await leaderboard.add_subscriber(websocket)
    
    try:
        while True:
            # Keep the connection open
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                print(f"Received message: {message}")
                if message.get('type') == 'update_score':
                    user_id = message.get('user_id')
                    points = message.get('points', 0)
                    if user_id is not None and points is not None:
                        await leaderboard.update_score(user_id, int(points))
            except json.JSONDecodeError:
                print(f"Received non-JSON message: {data}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        leaderboard.remove_subscriber(websocket)
        print("WebSocket connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)