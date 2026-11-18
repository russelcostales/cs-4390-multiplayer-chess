import { Chessboard } from 'react-chessboard';
import './App.css';

function App() {
  return (
    <div className="App">
      <Chessboard
        options={{
            id: 'demo-board',
            boardStyle: {
            borderRadius: '8px',
            overflow: 'hidden', // needed so the square corners don't poke past the rounded edge
            },
        }}
    />
    </div>
  );
}

export default App;