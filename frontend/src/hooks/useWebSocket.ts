// src/hooks/useWebSocket.ts
import { useEffect, useRef, useState } from 'react';

interface LeaderboardEntry {
  user_id: string;
  score: number;
}

export function useWebSocket() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Use the WebSocket URL from environment variables or fallback to localhost with port 8765
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8765/ws';
    console.log('Connecting to WebSocket at:', wsUrl);
    ws.current = new WebSocket(wsUrl);

    ws.current.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === 'leaderboard_update' && Array.isArray(data.data)) {
          setLeaderboard(data.data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.current.onerror = (event: Event) => {
      console.error('WebSocket error:', event);
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const updateScore = (userId: string, points: number): void => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      try {
        ws.current.send(JSON.stringify({
          type: 'update_score',
          user_id: userId,
          points: points
        }));
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
      }
    } else {
      console.error('WebSocket is not connected');
    }
  };

  return { leaderboard, updateScore };
}