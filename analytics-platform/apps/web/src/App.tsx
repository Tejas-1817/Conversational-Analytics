import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Layout } from './app/Layout';

// Pages
import { Login } from './pages/auth/Login';
import { DataSources } from './pages/admin/DataSources';
import { Jobs } from './pages/admin/Jobs';
import { SchemaExplorer } from './pages/admin/SchemaExplorer';
import { SemanticLayer } from './pages/admin/SemanticLayer';
import { Users } from './pages/admin/Users';
import { ReliabilityDashboard } from './pages/admin/ReliabilityDashboard';
import { Benchmarks } from './pages/admin/Benchmarks';
import { EvaluationRunDetails } from './pages/admin/EvaluationRunDetails';
import { ChatInterface } from './pages/business/ChatInterface';
import { Dashboards } from './pages/business/Dashboards';

const ProtectedRoute = ({ children, requireAdmin = false }: { children: React.ReactNode, requireAdmin?: boolean }) => {
  const { user, loading } = useAuth();
  
  if (loading) return <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (requireAdmin && user.role !== 'ADMIN') return <Navigate to="/chat" replace />;
  
  return <Layout>{children}</Layout>;
};

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        {/* Business Routes */}
        <Route path="/chat" element={<ProtectedRoute><ChatInterface /></ProtectedRoute>} />
        <Route path="/dashboards" element={<ProtectedRoute><Dashboards /></ProtectedRoute>} />
        
        {/* Admin Routes */}
        <Route path="/sources" element={<ProtectedRoute requireAdmin><DataSources /></ProtectedRoute>} />
        <Route path="/jobs" element={<ProtectedRoute requireAdmin><Jobs /></ProtectedRoute>} />
        <Route path="/explorer" element={<ProtectedRoute requireAdmin><SchemaExplorer /></ProtectedRoute>} />
        <Route path="/semantic" element={<ProtectedRoute requireAdmin><SemanticLayer /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute requireAdmin><Users /></ProtectedRoute>} />
        
        {/* Phase 7: Eval Routes */}
        <Route path="/eval/dashboard" element={<ProtectedRoute requireAdmin><ReliabilityDashboard /></ProtectedRoute>} />
        <Route path="/eval/benchmarks" element={<ProtectedRoute requireAdmin><Benchmarks /></ProtectedRoute>} />
        <Route path="/eval/runs/:id" element={<ProtectedRoute requireAdmin><EvaluationRunDetails /></ProtectedRoute>} />
        
        {/* Default Redirect */}
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </AuthProvider>
  );
}
