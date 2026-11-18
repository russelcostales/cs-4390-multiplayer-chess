import { Chessboard } from 'react-chessboard';
import { Box } from '@mui/material';
import PlayerRow from './PlayerRow';
import { LIGHT, DARK } from '../../constants';

export default function BoardColumn() {
  return (
    <Box sx={{ flex: '1 1 480px', maxWidth: 600, display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <PlayerRow prefix="—" label="Black" />

      <Box sx={{ width: '100%', lineHeight: 0 }}>
        <Chessboard
          options={{
            id: 'demo-board',
            boardStyle: {
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 0 0 1px #5b5b5b, 0 6px 18px rgba(0,0,0,0.55)',
            },
            lightSquareStyle: { backgroundColor: LIGHT },
            darkSquareStyle: { backgroundColor: DARK },
            lightSquareNotationStyle: { color: DARK, fontWeight: 600 },
            darkSquareNotationStyle: { color: LIGHT, fontWeight: 600 },
          }}
        />
      </Box>

      <PlayerRow prefix="You" label="White" />
    </Box>
  );
}