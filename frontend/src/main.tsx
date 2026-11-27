import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, CssBaseline, createTheme } from '@mui/material'
import App from './App.tsx'

// DEV ONLY: ?demo=ui renders the game UI harness. Remove with src/dev/ before merging.
const GameUiDemo =
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('demo') === 'ui'
    ? lazy(() => import('./dev/GameUiDemo.tsx'))
    : null;

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
      {GameUiDemo ? (
        <Suspense fallback={null}>
          <GameUiDemo />
        </Suspense>
      ) : (
        <App />
      )}
    </ThemeProvider>
  </StrictMode>,
)