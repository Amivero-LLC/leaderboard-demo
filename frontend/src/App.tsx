import { useEffect, useState } from 'react';
import { 
  ChakraProvider,
  Box, 
  Heading, 
  Input, 
  Button, 
  Container,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  VStack,
  HStack,
  TableContainer,
  extendTheme,
} from '@chakra-ui/react';

// Extend the theme to include custom colors, fonts, etc
const config = {
  initialColorMode: 'light',
  useSystemColorMode: false,
} as const;

const theme = extendTheme({
  config,
  styles: {
    global: {
      table: {
        bg: 'white',
      },
      th: {
        fontWeight: 'bold',
      },
    },
  },
});

interface PlayerScore {
  player_id: string;
  player_name: string;
  score: number;
  last_updated?: string;
}

function App() {
  const [scores, setScores] = useState<PlayerScore[]>([]);
  const [playerName, setPlayerName] = useState('');
  const [score, setScore] = useState('');
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    // Get WebSocket URL from environment variables with fallback
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8765';
    
    // Only connect if we have a valid URL
    if (!wsUrl) {
      console.error('WebSocket URL is not defined');
      return;
    }

    console.log('Connecting to WebSocket server at:', wsUrl);
    const websocket = new WebSocket(wsUrl);
    setWs(websocket);

    websocket.onopen = () => {
      console.log('Successfully connected to WebSocket server');
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'leaderboard_update') {
          console.log('Received leaderboard update:', data.data);
          setScores(data.data);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    websocket.onclose = (event) => {
      console.log('WebSocket connection closed:', event.code, event.reason);
      // Optionally implement reconnection logic here
    };

    // Cleanup function
    return () => {
      if (websocket.readyState === WebSocket.OPEN) {
        websocket.close();
      }
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!playerName || !score || !ws) return;

    const scoreData = {
      action: 'submit_score',
      player_id: `player_${Date.now()}`,
      player_name: playerName,
      score: parseInt(score, 10)
    };

    ws.send(JSON.stringify(scoreData));
    setPlayerName('');
    setScore('');
  };

  return (
    <ChakraProvider theme={theme}>
        <Container maxW="container.md" py={8}>
          <VStack spacing={8} align="stretch">
            <Box textAlign="center">
              <Heading as="h1" size="xl" mb={4}>
                Leaderboard
              </Heading>
            </Box>

            <Box>
              <form onSubmit={handleSubmit}>
                <HStack spacing={4} mb={8}>
                  <Input
                    placeholder="Your name"
                    value={playerName}
                    onChange={(e) => setPlayerName(e.target.value)}
                    required
                  />
                  <Input
                    type="number"
                    placeholder="Your score"
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                    required
                  />
                  <Button type="submit" colorScheme="blue">
                    Submit Score
                  </Button>
                </HStack>
              </form>
            </Box>

            <Box borderWidth="1px" borderRadius="lg" overflow="hidden">
              <TableContainer overflowX="auto">
                <Table variant="simple" size="md">
                  <Thead bg="gray.100">
                    <Tr>
                      <Th>Rank</Th>
                      <Th>Player</Th>
                      <Th textAlign="right">Score</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {scores.length > 0 ? (
                      scores.map((player, index) => (
                        <Tr key={player.player_id}>
                          <Td>{index + 1}</Td>
                          <Td>{player.player_name || 'Anonymous'}</Td>
                          <Td textAlign="right">{player.score}</Td>
                        </Tr>
                      ))
                    ) : (
                      <Tr>
                        <Td colSpan={3} textAlign="center">No scores yet</Td>
                      </Tr>
                    )}
                  </Tbody>
                </Table>
              </TableContainer>
            </Box>
          </VStack>
        </Container>
      </ChakraProvider>
  );

}

export default App;
