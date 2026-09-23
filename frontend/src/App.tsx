import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import TopicSelection from './pages/TopicSelection';
import RoleSelection from './pages/RoleSelection';
import ScenarioBuilder from './pages/ScenarioBuilder';
import ConversationScreen from './pages/ConversationScreen';
import SessionHistory from './pages/SessionHistory';
import './index.css';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-text-main)] font-sans">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/topics" element={<TopicSelection />} />
          <Route path="/roles" element={<RoleSelection />} />
          <Route path="/scenario" element={<ScenarioBuilder />} />
          <Route path="/conversation" element={<ConversationScreen />} />
          <Route path="/history" element={<SessionHistory />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
