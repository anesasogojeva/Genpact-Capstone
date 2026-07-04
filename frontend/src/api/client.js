import axios from 'axios';

function resolveApiBaseUrl() {
  const fromEnv = import.meta.env.VITE_API_URL?.trim();
  if (fromEnv) return fromEnv;
  return '/api';
}

const apiBaseURL = resolveApiBaseUrl();
const api = axios.create({ baseURL: apiBaseURL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function login(email, password) {
  const form = new URLSearchParams();
  form.append('username', email.trim().toLowerCase());
  form.append('password', password);
  const { data } = await api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

export async function getMe() {
  const { data } = await api.get('/auth/me');
  return data;
}

export async function updateMe(body) {
  const { data } = await api.put('/auth/me', body, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getResources(params) {
  const { data } = await api.get('/resources', { params });
  return data;
}

export async function getTeamDeskRecommendations(date = null) {
  const { data } = await api.get('/resources/recommendations/team', {
    params: date ? { date } : {},
  });
  return data;
}

export async function createResource(body) {
  const { data } = await api.post('/resources', body);
  return data;
}

export async function updateResource(id, body) {
  const { data } = await api.put(`/resources/${id}`, body);
  return data;
}

export async function deleteResource(id) {
  await api.delete(`/resources/${id}`);
}

export async function addFavorite(resourceId) {
  const { data } = await api.post(`/resources/${resourceId}/favorite`);
  return data;
}

export async function removeFavorite(resourceId) {
  const { data } = await api.delete(`/resources/${resourceId}/favorite`);
  return data;
}

export async function updateResourcePosition(id, floor_plan_x, floor_plan_y) {
  const { data } = await api.patch(`/resources/${id}/position`, {
    floor_plan_x,
    floor_plan_y,
  });
  return data;
}

export async function getFloors() {
  const { data } = await api.get('/resources/floors');
  return data;
}

export async function getZones(floor) {
  const { data } = await api.get('/resources/zones', {
    params: floor ? { floor } : {},
  });
  return data;
}

export async function getMyReservations() {
  const { data } = await api.get('/reservations/me');
  return data;
}

export async function getAllReservations(date = null) {
  const { data } = await api.get('/reservations', {
    params: date ? { date } : {},
  });
  return data;
}

export async function createReservation(resource_id, date, start_time = null, end_time = null, repeat_weeks = 0) {
  const { data } = await api.post('/reservations', {
    resource_id,
    date,
    start_time,
    end_time,
    repeat_weeks,
  });
  return data;
}

export async function cancelReservation(id) {
  const { data } = await api.delete(`/reservations/${id}`);
  return data;
}

export async function updateReservation(id, body) {
  const { data } = await api.put(`/reservations/${id}`, body);
  return data;
}

export async function getFloorPlans() {
  const { data } = await api.get('/floor-plans');
  return data;
}

export async function uploadFloorPlan(floor, file, building = 'HQ', name = '') {
  const form = new FormData();
  form.append('floor', floor);
  form.append('building', building);
  if (name) form.append('name', name);
  form.append('file', file);
  const { data } = await api.post('/floor-plans', form);
  return data;
}

export async function updateFloorPlan(id, body) {
  const { data } = await api.put(`/floor-plans/${id}`, body);
  return data;
}

export async function deleteFloorPlan(id) {
  const { data } = await api.delete(`/floor-plans/${id}`);
  return data;
}

export async function getEmployeeSummary() {
  const { data } = await api.get('/analytics/employee-summary');
  return data;
}

export async function getAnalyticsDashboard(days = 30) {
  const { data } = await api.get('/analytics/dashboard', { params: { days } });
  return data;
}

export async function downloadAnalyticsCsv(days = 30) {
  const { data } = await api.get('/analytics/export', {
    params: { days },
    responseType: 'blob',
  });
  return data;
}

export async function getBookingLimits() {
  const { data } = await api.get('/reservations/limits');
  return data;
}

export async function getAuditLogs() {
  const { data } = await api.get('/audit-logs');
  return data;
}

export async function refreshAuthToken() {
  const { data } = await api.post('/auth/refresh');
  localStorage.setItem('token', data.access_token);
  return data;
}

export async function downloadUsersCsv() {
  const { data } = await api.get('/users/export', { responseType: 'blob' });
  return data;
}

export async function getRecentActivity() {
  const { data } = await api.get('/analytics/recent-activity');
  return data;
}

export async function getUsers() {
  const { data } = await api.get('/users');
  return data;
}

export async function updateUser(userId, body) {
  const { data } = await api.put(`/users/${userId}`, body);
  return data;
}

export async function deleteUser(userId) {
  const { data } = await api.delete(`/users/${userId}`);
  return data;
}

export async function getTeamMembers() {
  const { data } = await api.get('/users/team-members');
  return data;
}

export async function getAvailableForTeam() {
  const { data } = await api.get('/users/available-for-team');
  return data;
}

export async function updateMyTeam(teamName, teammateIds) {
  const { data } = await api.put('/users/me/team', {
    team_name: teamName,
    teammate_ids: teammateIds,
  });
  return data;
}

export async function searchWorkspace(query) {
  const { data } = await api.get('/users/search', {
    params: { q: query },
  });
  return data;
}

export async function assignTeamMembers(leaderId, teammateIds, teamName) {
  const { data } = await api.post(`/users/${leaderId}/team`, {
    teammate_ids: teammateIds,
    team_name: teamName,
  });
  return data;
}

export async function registerUser(body) {
  const { data } = await api.post('/auth/register', body);
  return data;
}

export async function resetPassword(token, password) {
  const { data } = await api.post('/auth/reset-password', { token, password });
  return data;
}

export async function requestPasswordReset(email) {
  const { data } = await api.post('/auth/forgot-password', {
    email: email.trim().toLowerCase(),
  });
  return data;
}

export async function createTeamBookings(date, bookings, repeat_weeks = 0) {
  const { data } = await api.post('/reservations/team-bookings', { date, bookings, repeat_weeks });
  return data;
}

export async function sendAiChat(message, history = []) {
  const { data } = await api.post('/ai/chat', { message, history });
  return data;
}

export async function buildProjectTeam({ prompt, requiredSkills = [], teamSize = null }) {
  const { data } = await api.post('/ai/team-builder', {
    prompt,
    requiredSkills,
    teamSize,
  });
  return data;
}

export async function emergencyStaffing({ projectName, problem, requiredSkills = [], neededPeople = 2 }) {
  const { data } = await api.post('/ai/emergency-staffing', {
    projectName,
    problem,
    requiredSkills,
    neededPeople,
  });
  return data;
}
