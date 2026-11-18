import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, CssBaseline, createTheme } from '@mui/material'
import App from './App.tsx'

import '@fontsource/barlow-semi-condensed/400.css';
import '@fontsource/barlow-semi-condensed/500.css';
import '@fontsource/barlow-semi-condensed/700.css';

const theme = createTheme({
  typography: {
    fontFamily: "'Barlow Semi Condensed', sans-serif",
  },
  palette: {
    mode: 'dark',
    background: { default: '#151515' },
    text: { primary: '#ececec', secondary: '#959595' },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </StrictMode>,
)