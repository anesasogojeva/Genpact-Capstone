import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import { AuthProvider } from './context/AuthContext';
import { AdminRoute, ManagerRoute, ProtectedRoute } from './components/ProtectedRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import FloorPlan from './pages/FloorPlan';
import Reservations from './pages/Reservations';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminReservations from './pages/admin/Reservations';
import Resources from './pages/admin/Resources';
import FloorBuilder from './pages/admin/FloorBuilder';
import Analytics from './pages/admin/Analytics';
import Users from './pages/admin/Users';
import AuditLog from './pages/admin/AuditLog';
import TeamSettings from './pages/TeamSettings';
import TeamBuilder from './pages/TeamBuilder';
import ResetPassword from './pages/ResetPassword';
import AiAssistant from './pages/AiAssistant';
import Profile from './pages/Profile';
import EmergencyStaffing from './pages/EmergencyStaffing';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="assistant" element={<AiAssistant />} />
            <Route path="reservations" element={<Reservations />} />
            <Route path="floor-plan" element={<FloorPlan />} />
            <Route path="profile" element={<Profile />} />
            <Route path="team" element={<TeamSettings />} />
            <Route
              path="team-builder"
              element={
                <ManagerRoute>
                  <TeamBuilder />
                </ManagerRoute>
              }
            />
            <Route
              path="admin"
              element={
                <AdminRoute>
                  <AdminDashboard />
                </AdminRoute>
              }
            />
            <Route
              path="admin/reservations"
              element={
                <AdminRoute>
                  <AdminReservations />
                </AdminRoute>
              }
            />
            <Route
              path="admin/resources"
              element={
                <AdminRoute>
                  <Resources />
                </AdminRoute>
              }
            />
            <Route
              path="admin/builder"
              element={
                <AdminRoute>
                  <FloorBuilder />
                </AdminRoute>
              }
            />
            <Route
              path="admin/analytics"
              element={
                <ManagerRoute>
                  <Analytics />
                </ManagerRoute>
              }
            />
            <Route
              path="admin/users"
              element={
                <AdminRoute>
                  <Users />
                </AdminRoute>
              }
            />
            <Route
              path="emergency-staffing"
              element={
                <ManagerRoute>
                  <EmergencyStaffing />
                </ManagerRoute>
              }
            />
            <Route
              path="admin/audit"
              element={
                <AdminRoute>
                  <AuditLog />
                </AdminRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <ToastContainer
          position="top-right"
          autoClose={3500}
          newestOnTop
          closeOnClick
          pauseOnFocusLoss={false}
          theme="light"
        />
      </AuthProvider>
    </BrowserRouter>
  );
}
