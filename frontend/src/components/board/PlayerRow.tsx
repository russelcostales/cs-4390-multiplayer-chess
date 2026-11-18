import { Box, Typography } from '@mui/material';

interface PlayerRowProps {
  prefix: string;
  label: string;
}

export default function PlayerRow({ prefix, label }: PlayerRowProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px', height: 20, fontSize: 14 }}>
      <Box sx={{ width: 3, height: 16, borderRadius: '2px', bgcolor: '#404040' }} />
      <Typography component="span" sx={{ fontSize: 14 }}>{prefix}</Typography>
      <Typography component="span" sx={{ fontSize: 13, color: '#777' }}>{label}</Typography>
    </Box>
  );
}