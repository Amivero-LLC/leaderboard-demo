import asyncio
import json
from typing import Any, Dict, List, Set, Tuple
import heapq
from fastapi import WebSocket

class InMemoryLeaderboard:
    def __init__(self, top_k: int = 10):
        self.top_k = top_k
        self.scores: Dict[str, int] = {}  # player_id -> score
        self.heap: List[Tuple[int, str]] = []  # min-heap of (score, player_id)
        self.subscribers: Set[WebSocket] = set()

    async def add_subscriber(self, websocket: WebSocket):
        self.subscribers.add(websocket)
        await self._send_updates()

    def remove_subscriber(self, websocket: WebSocket):
        self.subscribers.discard(websocket)

    async def update_score(self, player_id: str, points: int):
        # Update the score
        self.scores[player_id] = self.scores.get(player_id, 0) + points
        current_score = self.scores[player_id]
        
        # Update the heap
        for i, (score, pid) in enumerate(self.heap):
            if pid == player_id:
                self.heap[i] = (current_score, player_id)
                heapq.heapify(self.heap)
                break
        else:
            if len(self.heap) < self.top_k:
                heapq.heappush(self.heap, (current_score, player_id))
            elif current_score > self.heap[0][0]:
                heapq.heappop(self.heap)
                heapq.heappush(self.heap, (current_score, player_id))
        
        await self._send_updates()

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get top K scores in descending order with O(n log k) time and O(k) space"""
        if not self.heap:
            return []
            
        # Create a max heap by negating the scores
        max_heap = [(-score, pid) for score, pid in self.heap]
        heapq.heapify(max_heap)
        
        # Get top k elements
        result = []
        
        for _ in range(min(len(max_heap), self.top_k)):
            if not max_heap:
                break
            # Get the current max (min of negative is max of positive)
            score, pid = heapq.heappop(max_heap)
            result.append((-score, pid))  # Convert back to positive score
        
        # Format the output as list of dicts
        return [{"player_id": pid, "score": score} for score, pid in result]

    async def _send_updates(self):
        """Send current leaderboard to all subscribers"""
        leaderboard = self.get_leaderboard()
        message = json.dumps({"type": "leaderboard_update", "data": leaderboard})
        for websocket in self.subscribers:
            try:
                await websocket.send(message)
            except Exception as e:
                print(f"Error sending message to WebSocket: {e}")
                self.remove_subscriber(websocket)
                
    def get_top_scores(self, num_scores: int) -> int:
        return self.get_leaderboard()[:num_scores]
        

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
    await leaderboard.add_subscriber(websocket)
    
    try:
        while True:
            # Keep the connection alive
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "update_score":
                    player_id = message.get("player_id")
                    points = message.get("points", 0)
                    if player_id is not None and isinstance(points, (int, float)):
                        await leaderboard.update_score(player_id, int(points))
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        leaderboard.remove_subscriber(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)