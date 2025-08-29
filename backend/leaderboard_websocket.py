import asyncio
import json
from typing import Dict, List, Set, Tuple
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
        for websocket in self.subscribers:
            try:
                await websocket.send_text(message)
            except:
                self.remove_subscriber(websocket)

# Global instance
leaderboard = InMemoryLeaderboard(top_k=10)