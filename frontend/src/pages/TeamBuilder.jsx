import { useState } from 'react';
import {
  Briefcase,
  Loader2,
  Sparkles,
  UsersRound,
} from 'lucide-react';
import { buildProjectTeam } from '../api/client';
import PageHeader from '../components/ui/PageHeader';
import { formatApiError } from '../lib/apiError';

const EXAMPLE_PROMPTS = [
  'I need a team for a new AI project',
  'Build a cross-functional squad for a customer portal launch',
  'Assemble a data platform team with strong Python and pipeline skills',
  'Recommend a balanced engineering team for an MVP with frontend and backend coverage',
];

const EXPERIENCE_STYLES = {
  junior: 'bg-sky-50 text-sky-700 ring-sky-200',
  mid: 'bg-amber-50 text-amber-700 ring-amber-200',
  senior: 'bg-violet-50 text-violet-700 ring-violet-200',
};

function parseSkillsInput(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function ExperienceBadge({ level }) {
  const normalized = level?.toLowerCase?.() ?? '';
  const style = EXPERIENCE_STYLES[normalized] ?? 'bg-slate-100 text-slate-600 ring-slate-200';
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ring-1 ${style}`}>
      {normalized || 'unknown'}
    </span>
  );
}

export default function TeamBuilder() {
  const [prompt, setPrompt] = useState('');
  const [requiredSkills, setRequiredSkills] = useState('');
  const [teamSize, setTeamSize] = useState('5');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setResult(null);

    const cleanedPrompt = prompt.trim();
    if (!cleanedPrompt) {
      setError('Describe the project or team you need.');
      return;
    }

    const parsedTeamSize = Number(teamSize);
    setLoading(true);
    try {
      const response = await buildProjectTeam({
        prompt: cleanedPrompt,
        requiredSkills: parseSkillsInput(requiredSkills),
        teamSize: Number.isFinite(parsedTeamSize) && parsedTeamSize >= 2 ? parsedTeamSize : null,
      });
      setResult(response);
    } catch (err) {
      setError(formatApiError(err, 'Could not build a team recommendation.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Project Team Builder"
        subtitle="AI-assisted staffing for managers — balance skills, experience, diversity, and availability"
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,420px)_1fr]">
        <form onSubmit={handleSubmit} className="card space-y-4 p-6">
          <div className="flex items-center gap-3 rounded-xl border border-brand-100 bg-brand-50/70 px-4 py-3 text-sm text-brand-900">
            <Sparkles size={18} className="shrink-0 text-brand-600" />
            <p>
              Uses real employee profiles from Users — skills, specialization, experience, and availability.
            </p>
          </div>

          <div>
            <label htmlFor="team-builder-prompt" className="mb-1.5 block text-sm font-medium text-slate-700">
              Project request
            </label>
            <textarea
              id="team-builder-prompt"
              rows={5}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. I need a team for a new AI project with backend APIs and ML modeling"
              className="input-field min-h-[120px] resize-y"
              required
            />
          </div>

          <div>
            <label htmlFor="team-builder-skills" className="mb-1.5 block text-sm font-medium text-slate-700">
              Required skills <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              id="team-builder-skills"
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              placeholder="Python, Machine Learning, React"
              className="input-field"
            />
            <p className="mt-1.5 text-xs text-slate-500">
              Comma-separated. Leave blank to infer skills from your project description.
            </p>
          </div>

          <div>
            <label htmlFor="team-builder-size" className="mb-1.5 block text-sm font-medium text-slate-700">
              Team size
            </label>
            <input
              id="team-builder-size"
              type="number"
              min="2"
              max="20"
              value={teamSize}
              onChange={(e) => setTeamSize(e.target.value)}
              className="input-field w-32"
            />
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Quick examples
            </p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setPrompt(example)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-left text-xs text-slate-600 transition hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary inline-flex items-center gap-2">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <UsersRound size={16} />}
            {loading ? 'Building team…' : 'Build recommended team'}
          </button>
        </form>

        <div className="space-y-4">
          {!result && !loading && (
            <div className="card flex min-h-[320px] flex-col items-center justify-center px-6 py-12 text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                <Briefcase size={28} strokeWidth={1.5} />
              </div>
              <h2 className="text-lg font-semibold text-slate-900">Recommended team will appear here</h2>
              <p className="mt-2 max-w-md text-sm text-slate-500">
                Submit a project brief and the agent will propose members from your organization with reasons for each pick.
              </p>
            </div>
          )}

          {loading && (
            <div className="card flex min-h-[320px] flex-col items-center justify-center px-6 py-12 text-center">
              <Loader2 size={32} className="animate-spin text-brand-600" />
              <p className="mt-4 text-sm font-medium text-slate-700">Analyzing employee profiles…</p>
              <p className="mt-1 text-xs text-slate-500">Ranking candidates and generating recommendations</p>
            </div>
          )}

          {result && (
            <>
              {result.isPartialMatch && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <p className="font-medium">
                    Partial match: found {result.matchedCount} of {result.requestedTeamSize} requested members.
                  </p>
                  <p className="mt-1 text-amber-800">
                    Showing the best available matches from employee profiles. Review skill gaps below.
                  </p>
                </div>
              )}

              <div className="card p-6">
                <div className="mb-3 flex items-center gap-2">
                  <Sparkles size={18} className="text-brand-600" />
                  <h2 className="text-lg font-semibold text-slate-900">Team summary</h2>
                </div>
                <p className="text-sm leading-relaxed text-slate-600">{result.summary}</p>
                <p className="mt-4 text-xs font-medium uppercase tracking-wide text-slate-400">
                  {result.matchedCount ?? result.team?.length ?? 0} recommended members
                  {result.requestedTeamSize ? ` · requested ${result.requestedTeamSize}` : ''}
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {(result.team ?? []).map((member) => (
                  <article key={`${member.name}-${member.role}`} className="card p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-slate-900">{member.name}</h3>
                        <p className="mt-0.5 text-sm text-slate-600">{member.role}</p>
                      </div>
                      <ExperienceBadge level={member.experienceLevel} />
                    </div>

                    {Array.isArray(member.skills) && member.skills.length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-1.5">
                        {member.skills.map((skill) => (
                          <span
                            key={`${member.name}-${skill}`}
                            className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    )}

                    <p className="mt-4 text-sm leading-relaxed text-slate-600">{member.reason}</p>
                  </article>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
