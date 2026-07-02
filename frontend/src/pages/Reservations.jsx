import { useEffect, useState } from 'react';
import { format, isAfter, isBefore, parseISO, startOfToday } from 'date-fns';
import { CalendarX, CheckCircle2, Clock, History } from 'lucide-react';
import { cancelReservation, getBookingLimits, getMyReservations } from '../api/client';
import MiniCalendar from '../components/MiniCalendar';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import KpiCard from '../components/ui/KpiCard';
import PageHeader from '../components/ui/PageHeader';
import { SkeletonCard, SkeletonTable } from '../components/ui/Skeleton';

export default function ReservationsPage() {
  const [reservations, setReservations] = useState([]);
  const [cancelling, setCancelling] = useState(null);
  const [cancelTarget, setCancelTarget] = useState(null);
  const [limits, setLimits] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => getMyReservations().then(setReservations);
  useEffect(() => {
    Promise.all([
      load(),
      getBookingLimits().then(setLimits).catch(() => setLimits(null)),
    ]).finally(() => setLoading(false));
  }, []);

  const today = startOfToday();
  const upcoming = reservations.filter(
    (r) =>
      r.status === 'active' &&
      (r.date === format(today, 'yyyy-MM-dd') || isAfter(parseISO(r.date), today)),
  );
  const completed = reservations.filter(
    (r) => r.status === 'active' && isBefore(parseISO(r.date), today),
  );
  const cancelled = reservations.filter((r) => r.status !== 'active');
  const highlightedDates = reservations
    .filter((r) => r.status === 'active')
    .map((r) => r.date);

  const handleCancelConfirm = async () => {
    if (!cancelTarget) return;
    setCancelling(cancelTarget.id);
    try {
      await cancelReservation(cancelTarget.id);
      setCancelTarget(null);
      await load();
    } finally {
      setCancelling(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="My Reservations"
        subtitle="View, manage and cancel your workspace bookings"
      />

      {limits && (
        <div className="mb-4 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800">
          Booking limits: up to <strong>{limits.max_active_reservations}</strong> active reservations,
          book up to <strong>{limits.max_booking_days_ahead}</strong> days ahead.
          You currently have <strong>{limits.active_reservations}</strong> active
          ({limits.remaining_slots} slot{limits.remaining_slots === 1 ? '' : 's'} remaining).
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <SkeletonCard key={index} rows={2} />
          ))}
        </div>
      ) : (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Upcoming" value={upcoming.length} icon={Clock} accent="bg-sky-50 text-sky-600" />
        <KpiCard label="Completed" value={completed.length} icon={CheckCircle2} accent="bg-emerald-50 text-emerald-600" />
        <KpiCard label="Cancelled" value={cancelled.length} icon={CalendarX} accent="bg-slate-100 text-slate-600" />
        <KpiCard label="Total Bookings" value={reservations.length} icon={History} accent="bg-violet-50 text-violet-600" />
      </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        {loading ? <SkeletonCard rows={8} /> : <MiniCalendar highlightedDates={highlightedDates} />}

        <div className="card lg:col-span-2">
          <div className="border-b border-slate-100 px-6 py-4">
            <h3 className="font-semibold text-slate-900">Upcoming Reservations</h3>
          </div>
          <div className="divide-y divide-slate-100 p-4">
            {loading ? (
              Array.from({ length: 3 }).map((_, index) => (
                <SkeletonCard key={index} rows={3} className="mb-3" />
              ))
            ) : upcoming.map((r) => (
              <div
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-4 rounded-xl p-4 transition hover:bg-slate-50"
              >
                <div className="flex items-start gap-4">
                  <div className="flex h-12 w-12 flex-col items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                    <span className="text-xs font-medium uppercase">
                      {format(parseISO(r.date), 'MMM')}
                    </span>
                    <span className="text-lg font-bold leading-none">
                      {format(parseISO(r.date), 'd')}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">{r.resource?.name}</p>
                    <p className="text-sm text-slate-500">
                      Floor {r.resource?.floor} · {r.resource?.zone} · {r.resource?.desk_type}
                    </p>
                    <span className="badge-green mt-2">Confirmed</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setCancelTarget(r)}
                  disabled={cancelling === r.id}
                  className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                >
                  {cancelling === r.id ? 'Cancelling…' : 'Cancel'}
                </button>
              </div>
            ))}
            {!loading && upcoming.length === 0 && (
              <p className="py-12 text-center text-slate-400">No upcoming reservations</p>
            )}
          </div>
        </div>
      </div>

      <div className="card mt-6 overflow-hidden">
        <div className="border-b border-slate-100 px-6 py-4">
          <h3 className="font-semibold text-slate-900">Booking History</h3>
        </div>
        {loading ? (
          <SkeletonTable rows={5} columns={5} />
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
              <tr key={r.id} className="border-t border-slate-100">
                <td className="px-6 py-3.5 font-medium">{r.resource?.name}</td>
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
                  <span
                    className={
                      r.status === 'active'
                        ? 'badge-green capitalize'
                        : r.status === 'cancelled'
                          ? 'badge-amber capitalize'
                          : 'badge-red capitalize'
                    }
                  >
                    {r.status.replace('_', ' ')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(cancelTarget)}
        title="Cancel reservation?"
        message={
          cancelTarget
            ? `${cancelTarget.resource?.name ?? 'This resource'} on ${cancelTarget.date} will be released and become available for other employees.`
            : ''
        }
        confirmLabel="Cancel reservation"
        cancelLabel="Keep reservation"
        loading={Boolean(cancelling)}
        onConfirm={handleCancelConfirm}
        onCancel={() => {
          if (!cancelling) setCancelTarget(null);
        }}
      />
    </div>
  );
}
