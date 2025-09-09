// src/components/Leaderboard.tsx
import { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';

export function Leaderboard() {
  const [userId, setUserId] = useState('');
  const [points, setPoints] = useState('');
  const { leaderboard, updateScore } = useWebSocket();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (userId && points) {
      updateScore(userId, parseInt(points, 10));
      setPoints('');
    }
  };

  return (
    <div>
      <h1>Leaderboard</h1>
      
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="User ID"
          required
        />
        <input
          type="number"
          value={points}
          onChange={(e) => setPoints(e.target.value)}
          placeholder="Points"
          required
        />
        <button type="submit">Add Points</button>
      </form>

      <div className="leaderboard">
        <h2>Top Scores</h2>
        {leaderboard.map((entry: { user_id: string; score: number }, index: number) => (
          <div key={entry.user_id} className="score-entry">
            <span>{index + 1}. {entry.user_id} </span>
            <span>{entry.score} points</span>
          </div>
        ))}
      </div>
    </div>
  );
}