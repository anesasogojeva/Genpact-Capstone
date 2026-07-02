import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import {
  Armchair,
  Building2,
  CalendarCheck,
  LocateFixed,
  Percent,
  Sparkles,
} from 'lucide-react';
import { getEmployeeSummary, getMyReservations } from '../api/client';
import KpiCard from '../components/ui/KpiCard';
import PageHeader from '../components/ui/PageHeader';
import { SkeletonCard, SkeletonTable } from '../components/ui/Skeleton';
import { useAuth } from '../context/AuthContext';

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    Promise.all([
      getEmployeeSummary().then(setSummary),
      getMyReservations().then((r) =>
        setReservations(r.filter((x) => x.status === 'active').slice(0, 6)),
      ),
    ]).finally(() => setLoading(false));
  }, []);

  const trendData =
    summary?.trend.map((t) => ({
      ...t,
      label: format(parseISO(t.date), 'EEE'),
    })) ?? [];

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Overview of today's workspace availability and your bookings"
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <SkeletonCard key={index} rows={2} />
          ))}
        </div>
      ) : (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Today's Occupancy"
          value={summary?.occupancy ?? '—'}
          suffix="%"
          icon={Percent}
          trend="+4% vs yesterday"
          trendUp
          accent="bg-violet-50 text-violet-600"
        />
        <KpiCard
          label="Available Desks"
          value={summary?.available_desks ?? '—'}
          icon={Armchair}
          accent="bg-emerald-50 text-emerald-600"
        />
        <KpiCard
          label="Available Rooms"
          value={summary?.available_rooms ?? '—'}
          icon={Building2}
          accent="bg-sky-50 text-sky-600"
        />
        <KpiCard
          label="My Reservations"
          value={summary?.my_reservations ?? '—'}
          icon={CalendarCheck}
          accent="bg-amber-50 text-amber-600"
        />
      </div>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <div className="card p-6 xl:col-span-2">
          <h3 className="font-semibold text-slate-900">Occupancy Trend</h3>
          <p className="text-sm text-slate-500">Last 7 days booking activity</p>
          {loading ? (
            <SkeletonCard rows={8} className="mt-4 shadow-none" />
          ) : (
          <ResponsiveContainer width="100%" height={240} className="mt-4">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} />
              <Tooltip
                contentStyle={{
                  borderRadius: 8,
                  border: '1px solid #e2e8f0',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                }}
              />
              <Line
                type="monotone"
                dataKey="booked"
                stroke="#0052cc"
                strokeWidth={2.5}
                dot={{ fill: '#0052cc', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
          )}
        </div>

        <div className="card p-6">
          <h3 className="font-semibold text-slate-900">Quick Actions</h3>
          <p className="text-sm text-slate-500">Reserve your workspace in seconds</p>
          <div className="mt-5 space-y-3">
            <Link to="/assistant" className="btn-primary w-full py-3">
              <Sparkles size={18} /> AI Assistant
            </Link>
            <Link to="/floor-plan" className="btn-secondary w-full py-3">
              <Armchair size={18} /> Reserve a seat
            </Link>
            <Link to="/floor-plan?type=room" className="btn-secondary w-full py-3">
              <Building2 size={18} /> Reserve Room
            </Link>
            {user?.role === 'employee' && user?.team_name && (
              <Link to="/floor-plan?nearTeam=1" className="btn-secondary w-full py-3">
                <LocateFixed size={18} /> Find me a desk near my team
              </Link>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="font-semibold text-slate-900">Floor Overview</h3>
          <p className="text-sm text-slate-500">Occupancy by floor today</p>
          {loading ? (
            <SkeletonCard rows={7} className="mt-4 shadow-none" />
          ) : (
          <ResponsiveContainer width="100%" height={220} className="mt-4">
            <BarChart data={summary?.floor_overview ?? []} layout="vertical" barSize={18}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <YAxis
                dataKey="floor"
                type="category"
                width={72}
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => `Floor ${v}`}
              />
              <Tooltip formatter={(v) => [`${v}%`, 'Occupancy']} />
              <Bar dataKey="occupancy" fill="#0052cc" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
          )}
        </div>

        <div className="card overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-4">
            <h3 className="font-semibold text-slate-900">Recent Reservations</h3>
            <p className="text-sm text-slate-500">Your upcoming bookings</p>
          </div>
          <div className="overflow-x-auto">
            {loading ? (
              <SkeletonTable rows={4} columns={5} />
            ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="px-6 py-3">Resource</th>
                  <th className="px-6 py-3">Floor</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Time Slot</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {reservations.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50/50">
                    <td className="px-6 py-3.5 font-medium text-slate-900">
                      {r.resource?.name}
                    </td>
                    <td className="px-6 py-3.5 text-slate-600">{r.resource?.floor}</td>
                    <td className="px-6 py-3.5 text-slate-600">{r.date}</td>
                    <td className="px-6 py-3.5 text-slate-600">
                      {r.start_time && r.end_time
                        ? `${String(r.start_time).slice(0, 5)} - ${String(r.end_time).slice(0, 5)}`
                        : r.resource?.type === 'room'
                          ? '—'
                          : 'All day'}
                    </td>
                    <td className="px-6 py-3.5">
                      <span className="badge-green capitalize">{r.status}</span>
                    </td>
                  </tr>
                ))}
                {reservations.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center text-slate-400">
                      No upcoming reservations —{' '}
                      <Link to="/floor-plan" className="text-brand-600 hover:underline">
                        book a desk
                      </Link>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
