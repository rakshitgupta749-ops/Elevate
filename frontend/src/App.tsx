import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RoleSelection from './pages/RoleSelection';
import ScenarioBuilder from './pages/ScenarioBuilder';
import ConversationScreen from './pages/ConversationScreen';
import SessionHistory from './pages/SessionHistory';
import AdminPage from './pages/AdminPage';
import { useStore } from './store/useStore';
import { WebGLBackground } from './components/WebGLBackground';
import './index.css';

// Protected Route wrapper: requires authenticated learner profile
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { learner } = useStore();
  if (!learner) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

// Admin Route wrapper: requires authenticated user with role === 'admin'
const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  const { learner } = useStore();
  if (!learner) {
    return <Navigate to="/login" replace />;
  }
  if (learner.role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
};

// Public Only Route: if already logged in, redirect straight to Home or Admin
const PublicOnlyRoute = ({ children }: { children: React.ReactNode }) => {
  const { learner } = useStore();
  if (learner) {
    if (learner.role === 'admin') {
      return <Navigate to="/admin" replace />;
    }
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
};

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-950 text-slate-100 font-sans relative selection:bg-indigo-500/30 selection:text-indigo-200">
        <WebGLBackground />
        <Routes>
          {/* 1. Login Page: Entry point for unauthenticated users */}
          <Route
            path="/login"
            element={
              <PublicOnlyRoute>
                <LoginPage />
              </PublicOnlyRoute>
            }
          />

          {/* 2. Home Page: Entry point after login */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <LandingPage />
              </ProtectedRoute>
            }
          />

          {/* 3. Different Routes accessible from Home */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <SessionHistory />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <SessionHistory />
              </ProtectedRoute>
            }
          />
          <Route
            path="/topics"
            element={<Navigate to="/roles" replace />}
          />
          <Route
            path="/roles"
            element={
              <ProtectedRoute>
                <RoleSelection />
              </ProtectedRoute>
            }
          />
          <Route
            path="/scenario"
            element={
              <ProtectedRoute>
                <ScenarioBuilder />
              </ProtectedRoute>
            }
          />
          <Route
            path="/conversation"
            element={
              <ProtectedRoute>
                <ConversationScreen />
              </ProtectedRoute>
            }
          />

          {/* Admin Studio Route */}
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />

          {/* Fallback to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
