import { useEffect, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import { MUTED } from '../../constants';

interface MoveHistoryProps {
  // moves in SAN, in order (white, black, white, ...)
  moves: string[];
}

export default function MoveHistory({ moves }: MoveHistoryProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // scroll to the newest move
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [moves.length]);

  if (moves.length === 0) {
    return <Typography sx={{ fontSize: 13, color: '#5b5b5b', pt: '12px' }}>No moves yet</Typography>;
  }

  // pair up moves so each row is one white move and one black move
  const rows = [];
  for (let i = 0; i < moves.length; i += 2) {
    rows.push({ num: i / 2 + 1, white: moves[i], black: moves[i + 1] });
  }

  const last = moves.length - 1;

  // highlight the most recent move
  const moveSx = (index: number) => ({
    fontSize: 13,
    px: '8px',
    py: '3px',
    borderRadius: '4px',
    color: index === last ? '#f4f4f4' : '#b4b4b4',
    backgroundColor: index === last ? 'rgba(63,138,87,.28)' : 'transparent',
  });

  return (
    <Box ref={scrollRef} sx={{ maxHeight: 320, overflowY: 'auto', pt: '8px' }}>
      {rows.map((row, i) => (
        <Box key={row.num} sx={{ display: 'grid', gridTemplateColumns: '36px 1fr 1fr', alignItems: 'center' }}>
          <Typography sx={{ fontSize: 13, color: MUTED, pl: '6px' }}>{row.num}.</Typography>
          <Typography sx={moveSx(i * 2)}>{row.white}</Typography>
          <Typography sx={moveSx(i * 2 + 1)}>{row.black ?? ''}</Typography>
        </Box>
      ))}
    </Box>
  );
}
