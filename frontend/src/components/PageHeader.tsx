import { Box, Typography } from '@mui/material';

export default function PageHeader() {
  return (
    <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '14px', py: '28px' }}>
      <Typography sx={{ fontSize: 15, fontWeight: 500, letterSpacing: '-0.01em' }}>
        Multiplayer Chess
      </Typography>
      <Typography sx={{ fontSize: 13, color: '#777' }}>CS 4390</Typography>
    </Box>
  );
}