import { Box } from '@mui/material';
import PageHeader from './components/PageHeader';
import BoardColumn from './components/board/BoardColumn';
import Sidebar from './components/sidebar/Sidebar';

export default function App() {
  return (
    <Box sx={{ maxWidth: 1080, mx: 'auto', px: '22px', pb: 6 }}>
      <PageHeader />
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: '48px', alignItems: 'stretch' }}>
        <BoardColumn />
        <Sidebar />
      </Box>
    </Box>
  );
}