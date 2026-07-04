import { useState } from 'react';
import { AlertTriangle, Loader2, UsersRound } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import { emergencyStaffing } from '../api/client';
import { formatApiError } from '../lib/apiError';

export default function EmergencyStaffing() {
  const [form, setForm] = useState({
    projectName: 'Payment API',
    problem: 'Senior backend developer is unavailable',
    requiredSkills: 'Python, FastAPI, PostgreSQL, Docker',
    neededPeople: 2,
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const skills = form.requiredSkills
    .split(',')
    .map((skill) => skill.trim())
    .filter(Boolean);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);
    setLoading(true);

    try {
      const data = await emergencyStaffing({
        projectName: form.projectName,
        problem: form.problem,
        requiredSkills: skills,
        neededPeople: Number(form.neededPeople),
      });
      setResult(data);
    } catch (err) {
      setError(formatApiError(err, 'Could not generate emergency staffing recommendations.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Emergency Staffing Agent"
        subtitle="Find available employees who can temporarily support urgent project needs"
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="card mb-6 grid gap-4 p-6">
        <div className="grid gap-4 md:grid-cols-2">
          <input
            className="input-field"
            placeholder="Project name"
            value={form.projectName}
            onChange={(e) => setForm({ ...form, projectName: e.target.value })}
            required
          />

          <input
            className="input-field"
            type="number"
            min="2"
            max="10"
            placeholder="Needed people"
            value={form.neededPeople}
            onChange={(e) => setForm({ ...form, neededPeople: e.target.value })}
            required
          />
        </div>

        <textarea
          className="input-field min-h-28"
          placeholder="What is the emergency?"
          value={form.problem}
          onChange={(e) => setForm({ ...form, problem: e.target.value })}
          required
        />

        <input
          className="input-field"
          placeholder="Required skills, comma-separated"
          value={form.requiredSkills}
          onChange={(e) => setForm({ ...form, requiredSkills: e.target.value })}
        />

        <button type="submit" className="btn-primary w-fit" disabled={loading}>
          {loading ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              Finding staff...
            </>
          ) : (
            <>
              <AlertTriangle size={18} />
              Find Emergency Staff
            </>
          )}
        </button>
      </form>

      {result && (
        <div className="card p-6">
          <div className="mb-4 flex items-center gap-2">
            <UsersRound className="text-brand-600" size={22} />
            <h3 className="text-lg font-semibold text-slate-900">Recommended People</h3>
          </div>

          <p className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {result.urgencyReason}
          </p>

          <p className="mb-5 text-sm text-slate-600">{result.summary}</p>

          <div className="grid gap-4 md:grid-cols-2">
            {(result.recommendedPeople ?? []).map((person, index) => (
              <div key={`${person.name}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-slate-900">{person.name}</h4>
                    <p className="text-sm text-slate-500">{person.role}</p>
                  </div>
                  <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium capitalize text-brand-700">
                    {person.experienceLevel ?? person.experience_level ?? 'mid'}
                  </span>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {(person.skills ?? []).map((skill) => (
                    <span key={skill} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                      {skill}
                    </span>
                  ))}
                </div>

                <p className="mt-3 text-sm text-slate-600">{person.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}