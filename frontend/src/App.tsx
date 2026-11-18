import { Chessboard } from 'react-chessboard';
import './App.css';

function App() {
  return (
    <div className="App">
      <Chessboard
        options={{
          id: 'demo-board',
        }}
      />
    </div>
  );
}

export default App;