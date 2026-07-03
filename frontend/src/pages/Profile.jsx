import { useEffect, useState } from 'react';
import { updateMe } from '../api/client';
import { useAuth } from '../context/AuthContext';
import PageHeader from '../components/ui/PageHeader';
import { formatApiError } from '../lib/apiError';

const DEPARTMENTS = ['Engineering', 'Data & AI', 'Product', 'Operations', 'Design', 'Platform'];

const SPECIALIZATIONS = [
  { value: 'frontend', label: 'Frontend' },
  { value: 'backend', label: 'Backend' },
  { value: 'fullstack', label: 'Full Stack' },
  { value: 'ai_ml', label: 'AI / ML' },
  { value: 'data_engineering', label: 'Data Engineering' },
  { value: 'data_science', label: 'Data Science' },
  { value: 'devops', label: 'DevOps' },
  { value: 'qa', label: 'QA / Testing' },
  { value: 'design', label: 'Design' },
  { value: 'product', label: 'Product' },
  { value: 'operations', label: 'Operations' },
  { value: 'general', label: 'General' },
];

const EXPERIENCE_LEVELS = [
  { value: 'junior', label: 'Junior' },
  { value: 'mid', label: 'Mid' },
  { value: 'senior', label: 'Senior' },
];

const EMPTY_FORM = {
  full_name: '',
  job_title: '',
  department: '',
  specialization: '',
  experience_level: '',
  skills: '',
  availability: '',
  current_password: '',
  new_password: '',
};

function formatSkillsInput(skills) {
  if (!Array.isArray(skills) || skills.length === 0) return '';
  return skills.join(', ');
}

export default function Profile() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState(EMPTY_FORM);
  const [profileImage, setProfileImage] = useState(null);
  const [preview, setPreview] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    setForm({
      full_name: user.full_name || '',
      job_title: user.job_title ?? '',
      department: user.department ?? '',
      specialization: user.specialization ?? '',
      experience_level: user.experience_level ?? '',
      skills: formatSkillsInput(user.skills),
      availability: user.availability != null ? String(Math.round(user.availability * 100)) : '',
      current_password: '',
      new_password: '',
    });
    setPreview(user.profile_image_path || '');
  }, [user]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage('');
    setError('');
    setSaving(true);

    try {
      const body = new FormData();
      body.append('full_name', form.full_name.trim());
      body.append('job_title', form.job_title.trim());
      body.append('department', form.department);
      body.append('specialization', form.specialization);
      body.append('experience_level', form.experience_level);
      body.append('skills', form.skills.trim());
      body.append('availability', form.availability);
      if (form.current_password) body.append('current_password', form.current_password);
      if (form.new_password) body.append('new_password', form.new_password);
      if (profileImage) body.append('profile_image', profileImage);

      const updated = await updateMe(body);
      setMessage('Profile updated successfully.');
      setForm((prev) => ({
        ...prev,
        full_name: updated.full_name,
        job_title: updated.job_title ?? '',
        department: updated.department ?? '',
        specialization: updated.specialization ?? '',
        experience_level: updated.experience_level ?? '',
        skills: formatSkillsInput(updated.skills),
        availability: updated.availability != null ? String(Math.round(updated.availability * 100)) : '',
        current_password: '',
        new_password: '',
      }));
      setProfileImage(null);
      setPreview(updated.profile_image_path || '');
      await refreshUser();
    } catch (err) {
      setError(formatApiError(err, 'Could not update profile.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="My Profile"
        subtitle="Update your work details, skills, and account settings"
      />

      <div className="card p-6">
        <div className="mb-6 flex items-center gap-4">
          <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-brand-600 text-2xl font-bold text-white">
            {preview ? <img src={preview} alt="" className="h-full w-full object-cover" /> : user?.full_name?.charAt(0)}
          </div>
          <div>
            <p className="text-lg font-semibold text-slate-900">{user?.full_name}</p>
            <p className="text-sm text-slate-500">{user?.email}</p>
            {user?.role && (
              <p className="mt-1 text-xs capitalize text-slate-400">{user.role.replace('_', ' ')}</p>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <p className="text-sm font-semibold text-slate-900">Work profile</p>
            <p className="text-xs text-slate-500">
              Used by the Project Team Builder and internal staffing recommendations.
            </p>
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Full name</label>
            <input
              className="input-field"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Job title</label>
            <input
              className="input-field"
              value={form.job_title}
              onChange={(e) => setForm({ ...form, job_title: e.target.value })}
              placeholder="e.g. Frontend Engineer"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Department</label>
            <select
              className="input-field"
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
            >
              <option value="">Select department</option>
              {DEPARTMENTS.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Specialization</label>
            <select
              className="input-field"
              value={form.specialization}
              onChange={(e) => setForm({ ...form, specialization: e.target.value })}
            >
              <option value="">Select specialization</option>
              {SPECIALIZATIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Experience level</label>
            <select
              className="input-field"
              value={form.experience_level}
              onChange={(e) => setForm({ ...form, experience_level: e.target.value })}
            >
              <option value="">Select experience</option>
              {EXPERIENCE_LEVELS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Skills</label>
            <input
              className="input-field"
              value={form.skills}
              onChange={(e) => setForm({ ...form, skills: e.target.value })}
              placeholder="React, Python, UX Design"
            />
            <p className="mt-1.5 text-xs text-slate-500">Comma-separated list of your key skills.</p>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Availability</label>
            <input
              type="number"
              min="0"
              max="100"
              className="input-field"
              value={form.availability}
              onChange={(e) => setForm({ ...form, availability: e.target.value })}
              placeholder="e.g. 80"
            />
            <p className="mt-1.5 text-xs text-slate-500">Optional percentage for project staffing (0–100).</p>
          </div>

          <div className="sm:col-span-2 border-t border-slate-100 pt-4">
            <p className="text-sm font-semibold text-slate-900">Account</p>
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Profile picture</label>
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="input-field py-2"
              onChange={(e) => setProfileImage(e.target.files?.[0] ?? null)}
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">Current password</label>
            <input
              type="password"
              className="input-field"
              value={form.current_password}
              onChange={(e) => setForm({ ...form, current_password: e.target.value })}
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">New password</label>
            <input
              type="password"
              className="input-field"
              value={form.new_password}
              onChange={(e) => setForm({ ...form, new_password: e.target.value })}
            />
          </div>

          {error && (
            <div className="sm:col-span-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {message && (
            <div className="sm:col-span-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              {message}
            </div>
          )}

          <div className="sm:col-span-2 flex gap-3">
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
