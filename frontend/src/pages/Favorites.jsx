import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { Heart, MapPin } from 'lucide-react';
import { format } from 'date-fns';
import { getFavoriteResources, removeFavorite } from '../api/client';
import { DESK_IMAGES } from '../lib/constants';
import PageHeader from '../components/ui/PageHeader';
import { SkeletonCard } from '../components/ui/Skeleton';

export default function Favorites() {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState(null);
  const navigate = useNavigate();

  const load = () => {
    const today = format(new Date(), 'yyyy-MM-dd');
    return getFavoriteResources(today).then(setResources);
  };

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, []);

  const handleRemove = async (resource) => {
    setRemovingId(resource.id);
    try {
      await removeFavorite(resource.id);
      setResources((prev) => prev.filter((r) => r.id !== resource.id));
      toast.success(`${resource.name} removed from favorites.`);
    } catch {
      toast.error('Could not remove favorite.');
    } finally {
      setRemovingId(null);
    }
  };

  const handleReserve = (resource) => {
    const params = new URLSearchParams({
      resourceId: String(resource.id),
      floor: resource.floor,
      type: resource.type,
    });
    navigate(`/floor-plan?${params.toString()}`);
  };

  return (
    <div>
      <PageHeader
        title="My Favorites"
        subtitle="Quick access to the desks and rooms you've starred"
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <SkeletonCard key={index} rows={3} />
          ))}
        </div>
      ) : resources.length === 0 ? (
        <div className="card flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-500">
            <Heart size={22} />
          </div>
          <h3 className="font-semibold text-slate-900">No favorites yet</h3>
          <p className="max-w-sm text-sm text-slate-500">
            Open a desk or room on the floor plan and tap "Add to Favorites" to see it here.
          </p>
          <button type="button" onClick={() => navigate('/floor-plan')} className="btn-primary mt-2">
            Browse the floor plan
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {resources.map((resource) => {
            const image = DESK_IMAGES[resource.desk_type ?? ''] ?? DESK_IMAGES.default;
            return (
              <div key={resource.id} className="card overflow-hidden">
                <div className="relative h-32 w-full overflow-hidden bg-slate-100">
                  <img src={image} alt="" className="h-full w-full object-cover" />
                  <button
                    type="button"
                    onClick={() => handleRemove(resource)}
                    disabled={removingId === resource.id}
                    aria-label="Remove from favorites"
                    className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-rose-500 shadow-sm transition hover:bg-white disabled:opacity-50"
                  >
                    <Heart size={16} fill="currentColor" />
                  </button>
                </div>
                <div className="p-4">
                  <p className="font-semibold text-slate-900">{resource.name}</p>
                  <p className="mt-1 flex items-center gap-1 text-sm text-slate-500">
                    <MapPin size={14} />
                    Floor {resource.floor} · {resource.zone}
                  </p>
                  <div className="mt-3 flex items-center justify-between">
                    {resource.is_available === false ? (
                      <span className="badge-red capitalize">
                        {resource.is_mine ? 'Reserved by you' : `Taken by ${resource.reserved_by ?? 'someone'}`}
                      </span>
                    ) : (
                      <span className="badge-green">Available today</span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleReserve(resource)}
                      className="btn-secondary px-3 py-1.5 text-sm"
                    >
                      View
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
