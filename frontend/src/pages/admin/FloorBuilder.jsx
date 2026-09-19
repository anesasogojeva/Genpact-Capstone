import { useEffect, useMemo, useRef, useState } from 'react';
import { Pencil, Trash2, Upload, X } from 'lucide-react';
import { toast } from 'react-toastify';
import {
  createResource,
  deleteFloorPlan,
  getFloorPlans,
  getResources,
  updateFloorPlan,
  updateResourcePosition,
  uploadFloorPlan,
} from '../../api/client';
import PageHeader from '../../components/ui/PageHeader';
import { sortByNaturalFloor, sortByNaturalName } from '../../lib/sort';
import { showConfirmToast } from '../../lib/toast';

const emptyPlanForm = {
  name: '',
  building: 'HQ - Prishtina',
  floor: '1',
};

const emptyNewFloorForm = {
  floor: '',
  name: '',
  building: 'HQ - Prishtina',
};

const emptyResourceForm = {
  name: '',
  type: 'desk',
  building: 'HQ - Prishtina',
  floor: '',
  zone: 'Open Area',
  capacity: 1,
  desk_type: 'Hot Desk',
  amenities: '',
};

const AMENITY_TYPES = ['Kitchen', 'Library', 'Break Area', 'Printer Area', 'Reception'];

const withFreshImage = (plan) => ({
  ...plan,
  image_url: `${plan.image_url}${plan.image_url.includes('?') ? '&' : '?'}v=${Date.now()}`,
});

export default function FloorBuilder() {
  const [floor, setFloor] = useState('');
  const [resources, setResources] = useState([]);
  const [plans, setPlans] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [planForm, setPlanForm] = useState(emptyPlanForm);
  const [resourceForm, setResourceForm] = useState(emptyResourceForm);
  const [creatingResource, setCreatingResource] = useState(false);
  const [editingPlanId, setEditingPlanId] = useState(null);
  const [savingPlan, setSavingPlan] = useState(false);
  const [savingResource, setSavingResource] = useState(false);
  const [message, setMessage] = useState('');
  const [missingPlanImages, setMissingPlanImages] = useState({});
  const [addingFloor, setAddingFloor] = useState(false);
  const [newFloorForm, setNewFloorForm] = useState(emptyNewFloorForm);
  const [creatingFloor, setCreatingFloor] = useState(false);
  const fileInputRef = useRef(null);
  const newFloorFileRef = useRef(null);
  const canvasRef = useRef(null);
  const dragActiveRef = useRef(false);
  const justDraggedRef = useRef(false);

  useEffect(() => {
    getFloorPlans()
      .then((data) => {
        const sorted = sortByNaturalFloor(data);
        setPlans(sorted);
        if (sorted.length) {
          setFloor(sorted[0].floor);
        } else {
          setPlanForm(emptyPlanForm);
        }
      })
      .catch(() => {
        setMessage('Could not load floor plans right now.');
        toast.error('Could not load floor plans right now.');
      });
  }, []);

  useEffect(() => {
    if (!floor) {
      setResources([]);
      return;
    }

    getResources({ floor }).then((data) => setResources(sortByNaturalName(data))).catch(() => setResources([]));
  }, [floor]);

  const plan = plans.find((item) => item.floor === floor) ?? null;
  const headerTitle = plan ? `Floor Plan Builder - ${plan.name || `Floor ${plan.floor}`}` : 'Floor Plan Builder';
  const headerSubtitle = plan
    ? `Upload, rename, replace, and manage the ${plan.building} floor plan while positioning resources`
    : 'Upload, rename, replace, and manage HQ floor plans while positioning resources';

  useEffect(() => {
    if (!floor) return;
    setResourceForm((current) => ({
      ...current,
      floor: current.floor || floor,
      building: current.building || plan?.building || 'HQ - Prishtina',
    }));
  }, [floor, plan]);

  useEffect(() => {
    if (editingPlanId) return;
    if (plan) {
      setPlanForm({ name: plan.name || `Floor ${plan.floor}`, building: plan.building, floor: plan.floor });
    } else if (floor) {
      setPlanForm((prev) => ({ ...prev, floor }));
    }
  }, [plan, floor, editingPlanId]);

  const floorOptions = useMemo(
    () =>
      [...new Set(plans.map((item) => item.floor).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, undefined, { numeric: true }),
      ),
    [plans],
  );

  const reloadPlans = async () => {
    const data = await getFloorPlans();
    const sorted = sortByNaturalFloor(data);
    setPlans(sorted);
    return sorted;
  };

  const startEditingPlan = (selectedPlan) => {
    setSelectedPlanId(selectedPlan.id);
    setEditingPlanId(selectedPlan.id);
    setPlanForm({
      name: selectedPlan.name || `Floor ${selectedPlan.floor}`,
      building: selectedPlan.building,
      floor: selectedPlan.floor,
    });
    setFloor(selectedPlan.floor);
    setMessage('');
  };

  const cancelEditingPlan = () => {
    setEditingPlanId(null);
    setSelectedPlanId(null);
    if (plan) {
      setPlanForm({ name: plan.name || `Floor ${plan.floor}`, building: plan.building, floor: plan.floor });
    } else {
      setPlanForm(emptyPlanForm);
    }
    setMessage('');
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !planForm.floor.trim()) return;

    setSavingPlan(true);
    setMessage('');
    try {
      const uploaded = await uploadFloorPlan(
        planForm.floor.trim(),
        file,
        planForm.building.trim() || 'HQ - Prishtina',
        planForm.name.trim() || `Floor ${planForm.floor.trim()}`,
      );
      const refreshedPlan = withFreshImage(uploaded);
      setPlans((prev) => {
        const rest = prev.filter((item) => item.id !== uploaded.id && item.floor !== uploaded.floor);
        return sortByNaturalFloor([...rest, refreshedPlan]);
      });
      setMissingPlanImages((current) => {
        const next = { ...current };
        delete next[uploaded.id];
        return next;
      });
      setFloor(uploaded.floor);
      setEditingPlanId(null);
      setMessage(`Floor plan for floor ${uploaded.floor} saved successfully.`);
      toast.success(`Floor plan for floor ${uploaded.floor} saved.`);
    } catch (error) {
      const errorMessage = error?.response?.data?.detail ?? 'Could not upload the floor plan.';
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      setSavingPlan(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleCreateFloor = async (e) => {
    const file = e.target.files?.[0];
    const newFloor = newFloorForm.floor.trim();
    if (!file || !newFloor) return;

    if (floorOptions.some((item) => item.toLowerCase() === newFloor.toLowerCase())) {
      toast.error(`Floor ${newFloor} already exists.`);
      if (newFloorFileRef.current) newFloorFileRef.current.value = '';
      return;
    }

    setCreatingFloor(true);
    try {
      const created = await uploadFloorPlan(
        newFloor,
        file,
        newFloorForm.building.trim() || 'HQ - Prishtina',
        newFloorForm.name.trim() || `Floor ${newFloor}`,
      );
      await reloadPlans();
      setFloor(created.floor);
      setAddingFloor(false);
      setNewFloorForm(emptyNewFloorForm);
      toast.success(`Floor ${created.floor} added.`);
    } catch (error) {
      const errorMessage = error?.response?.data?.detail ?? 'Could not create this floor.';
      toast.error(errorMessage);
    } finally {
      setCreatingFloor(false);
      if (newFloorFileRef.current) newFloorFileRef.current.value = '';
    }
  };

  const handleSavePlanDetails = async () => {
    if (!editingPlanId) return;

    setSavingPlan(true);
    setMessage('');
    try {
      const updated = await updateFloorPlan(editingPlanId, {
        name: planForm.name.trim() || `Floor ${planForm.floor.trim()}`,
        building: planForm.building.trim() || 'HQ - Prishtina',
        floor: planForm.floor.trim(),
      });
      const sorted = await reloadPlans();
      setFloor(updated.floor);
      setEditingPlanId(null);
      setSelectedPlanId(null);
      if (!sorted.find((item) => item.floor === updated.floor)) {
        setFloor(sorted[0]?.floor ?? '');
      }
      setMessage(`Floor ${updated.floor} updated successfully.`);
      toast.success(`Floor ${updated.floor} updated.`);
    } catch (error) {
      const errorMessage = error?.response?.data?.detail ?? 'Could not update this floor plan.';
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      setSavingPlan(false);
    }
  };

  const handleDeletePlan = async (selectedPlan) => {
    showConfirmToast({
      message: `Delete the floor plan for floor ${selectedPlan.floor}?`,
      confirmLabel: 'Delete floor',
      onConfirm: async () => {
        setSavingPlan(true);
        setMessage('');
        try {
          await deleteFloorPlan(selectedPlan.id);
          const nextPlans = await reloadPlans();
          const nextFloor = nextPlans[0]?.floor ?? '';
          setFloor(floor === selectedPlan.floor ? nextFloor : floor);
          if (editingPlanId === selectedPlan.id) setEditingPlanId(null);
          if (selectedPlanId === selectedPlan.id) setSelectedPlanId(null);
          setMessage(`Floor ${selectedPlan.floor} deleted successfully.`);
          toast.success(`Floor ${selectedPlan.floor} deleted.`);
        } catch (error) {
          const errorMessage = error?.response?.data?.detail ?? 'Could not delete this floor plan.';
          setMessage(errorMessage);
          toast.error(errorMessage);
        } finally {
          setSavingPlan(false);
        }
      },
    });
  };

  const handleCreateResource = async () => {
    if (!resourceForm.name.trim() || !resourceForm.floor.trim()) return;

    setSavingResource(true);
    setMessage('');
    const resourceFloor = resourceForm.floor.trim();
    try {
      const created = await createResource({
        ...resourceForm,
        name: resourceForm.name.trim(),
        building: resourceForm.building.trim() || plan?.building || 'HQ - Prishtina',
        floor: resourceFloor,
        zone: resourceForm.zone.trim(),
        amenities: resourceForm.amenities.trim() || undefined,
        capacity: resourceForm.type === 'amenity' ? 0 : resourceForm.capacity,
        desk_type:
          resourceForm.type === 'room'
            ? 'Meeting Room'
            : resourceForm.type === 'amenity'
              ? resourceForm.desk_type.trim() || 'Amenity'
              : resourceForm.desk_type.trim() || undefined,
      });
      const updated = await getResources({ floor: resourceFloor });
      setFloor(resourceFloor);
      setResources(sortByNaturalName(updated));
      setSelected(created);
      setResourceForm({
        ...emptyResourceForm,
        floor: resourceFloor || floor || plan?.floor || '',
        building: plan?.building || 'HQ - Prishtina',
      });
      setCreatingResource(false);
      setMessage('Resource saved successfully and is now available across the app.');
      toast.success(`${created.name} saved. Select it and click the plan to place its pin.`);
    } catch (error) {
      const errorMessage = error?.response?.data?.detail ?? 'Could not save this resource.';
      setMessage(errorMessage);
      toast.error(errorMessage);
    } finally {
      setSavingResource(false);
    }
  };

  const handleCanvasClick = async (e) => {
    if (justDraggedRef.current) {
      justDraggedRef.current = false;
      return;
    }
    if (!selected || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    await updateResourcePosition(selected.id, x, y);
    setResources((prev) =>
      prev.map((resource) =>
        resource.id === selected.id ? { ...resource, floor_plan_x: x, floor_plan_y: y } : resource,
      ),
    );
    toast.success(`${selected.name} pin placed.`);
  };

  const handleDrag = (e, resource) => {
    if (!canvasRef.current) return;
    e.preventDefault();
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
    setResources((prev) =>
      prev.map((item) =>
        item.id === resource.id ? { ...item, floor_plan_x: x, floor_plan_y: y } : item,
      ),
    );
  };

  const handleDragEnd = async (resource) => {
    if (!dragActiveRef.current) return;
    dragActiveRef.current = false;
    justDraggedRef.current = true;
    if (resource.floor_plan_x == null || resource.floor_plan_y == null) return;
    await updateResourcePosition(resource.id, resource.floor_plan_x, resource.floor_plan_y);
    toast.success(`${resource.name} pin updated.`);
    setDragging(null);
  };

  return (
    <div>
      <PageHeader
        title={headerTitle}
        subtitle={headerSubtitle}
      />

      {message && (
        <div className="mb-4 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
          {message}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <div className="card mb-4 flex flex-wrap items-center gap-4 p-4">
            <select
              value={floor}
              onChange={(e) => {
                setFloor(e.target.value);
                setEditingPlanId(null);
                setSelectedPlanId(null);
                setMessage('');
              }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {floorOptions.length > 0 ? (
                floorOptions.map((item) => (
                  <option key={item} value={item}>
                    Floor {item}
                  </option>
                ))
              ) : (
                <option value="">No floor plans yet</option>
              )}
            </select>

            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50">
              <Upload size={16} />
              {plan ? 'Replace floor plan' : 'Upload floor plan'}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleUpload}
              />
            </label>

            <button
              type="button"
              onClick={() => {
                setAddingFloor((current) => !current);
                setNewFloorForm(emptyNewFloorForm);
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-brand-200 px-4 py-2 text-sm text-brand-700 hover:bg-brand-50"
            >
              {addingFloor ? 'Cancel' : '+ Add Floor'}
            </button>

            {plan && !editingPlanId && (
              <>
                <button
                  type="button"
                  onClick={() => startEditingPlan(plan)}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm text-brand-700 hover:bg-slate-50"
                >
                  <Pencil size={16} />
                  Edit floor details
                </button>
                <button
                  type="button"
                  onClick={() => handleDeletePlan(plan)}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  <Trash2 size={16} />
                  Delete floor
                </button>
              </>
            )}

            {selected && (
              <p className="text-sm text-slate-500">
                Selected: <strong>{selected.name}</strong> - click canvas to place or drag pin
              </p>
            )}
          </div>

          {addingFloor && (
            <div className="card mb-4 p-4">
              <h4 className="text-sm font-semibold text-slate-900">Add a new floor</h4>
              <p className="mt-1 text-xs text-slate-500">
                Give the new floor a number or name, then choose its floor plan image to create it.
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <input
                  value={newFloorForm.floor}
                  onChange={(e) => setNewFloorForm({ ...newFloorForm, floor: e.target.value })}
                  placeholder="Floor number (e.g. 2)"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  value={newFloorForm.name}
                  onChange={(e) => setNewFloorForm({ ...newFloorForm, name: e.target.value })}
                  placeholder="Floor name (optional)"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  value={newFloorForm.building}
                  onChange={(e) => setNewFloorForm({ ...newFloorForm, building: e.target.value })}
                  placeholder="Building"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <label
                className={`mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 ${
                  !newFloorForm.floor.trim() || creatingFloor ? 'pointer-events-none opacity-50' : ''
                }`}
              >
                <Upload size={16} />
                {creatingFloor ? 'Creating...' : 'Choose floor plan image & create'}
                <input
                  ref={newFloorFileRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={!newFloorForm.floor.trim() || creatingFloor}
                  onChange={handleCreateFloor}
                />
              </label>
            </div>
          )}

          <div className="card mb-4 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold text-slate-900">Add Resource</h4>
                <p className="text-xs text-slate-500">
                  Create a bookable desk/room or a non-bookable amenity label such as Kitchen or Library.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCreatingResource((current) => !current)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {creatingResource ? 'Close' : 'New Resource'}
              </button>
            </div>

            {creatingResource && (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <input
                  value={resourceForm.name}
                  onChange={(e) => setResourceForm({ ...resourceForm, name: e.target.value })}
                  placeholder="Resource name"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <select
                  value={resourceForm.type}
                  onChange={(e) =>
                    setResourceForm({
                      ...resourceForm,
                      type: e.target.value,
                      desk_type:
                        e.target.value === 'room'
                          ? 'Meeting Room'
                          : e.target.value === 'amenity'
                            ? 'Kitchen'
                            : resourceForm.desk_type,
                      capacity: e.target.value === 'amenity' ? 0 : resourceForm.capacity || 1,
                    })
                  }
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="desk">Desk</option>
                  <option value="room">Meeting Room</option>
                  <option value="amenity">Amenity marker</option>
                </select>
                <input
                  value={resourceForm.floor}
                  onChange={(e) => setResourceForm({ ...resourceForm, floor: e.target.value })}
                  placeholder="Floor"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  value={resourceForm.building}
                  onChange={(e) => setResourceForm({ ...resourceForm, building: e.target.value })}
                  placeholder="HQ location"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  value={resourceForm.zone}
                  onChange={(e) => setResourceForm({ ...resourceForm, zone: e.target.value })}
                  placeholder="Zone"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <input
                  type="number"
                  min="1"
                  value={resourceForm.capacity}
                  onChange={(e) => setResourceForm({ ...resourceForm, capacity: Number(e.target.value) })}
                  placeholder="Capacity"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  disabled={resourceForm.type === 'amenity'}
                />
                {resourceForm.type === 'desk' ? (
                  <input
                    value={resourceForm.desk_type}
                    onChange={(e) => setResourceForm({ ...resourceForm, desk_type: e.target.value })}
                    placeholder="Desk type"
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-2"
                  />
                ) : resourceForm.type === 'amenity' ? (
                  <select
                    value={resourceForm.desk_type}
                    onChange={(e) => setResourceForm({ ...resourceForm, desk_type: e.target.value })}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-2"
                  >
                    {AMENITY_TYPES.map((amenity) => (
                      <option key={amenity} value={amenity}>
                        {amenity}
                      </option>
                    ))}
                  </select>
                ) : null}
                <input
                  value={resourceForm.amenities}
                  onChange={(e) => setResourceForm({ ...resourceForm, amenities: e.target.value })}
                  placeholder="Amenities, comma-separated"
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-2"
                />
                <div className="flex gap-2 sm:col-span-2">
                  <button
                    type="button"
                    onClick={handleCreateResource}
                    disabled={savingResource}
                    className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                  >
                    {savingResource ? 'Saving...' : 'Save Resource'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCreatingResource(false);
                      setResourceForm({
                        ...emptyResourceForm,
                        floor: floor || plan?.floor || '',
                        building: plan?.building || 'HQ - Prishtina',
                      });
                    }}
                    className="rounded-lg border border-slate-300 px-4 py-2 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="flex gap-4">
            <div className="card w-56 shrink-0 space-y-2 p-4">
              <h4 className="text-sm font-semibold">Resources on floor {floor || '-'}</h4>
              {resources.map((resource) => (
                <button
                  key={resource.id}
                  type="button"
                  onClick={() => setSelected(resource)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                    selected?.id === resource.id
                      ? 'border-brand-600 bg-brand-50'
                      : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {resource.name}
                  <span className="block text-xs text-slate-400">
                    {resource.type === 'amenity' ? 'Amenity marker' : resource.building} - {resource.zone}
                  </span>
                </button>
              ))}
              {resources.length === 0 && (
                <p className="text-xs text-slate-400">No resources mapped to this floor yet.</p>
              )}
            </div>

            <div className="flex min-h-[520px] flex-1 items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-slate-300 bg-slate-100 p-3">
              {plan ? (
                <div
                  ref={canvasRef}
                  onClick={handleCanvasClick}
                  className="relative max-h-[720px] w-full cursor-crosshair"
                >
                  {!missingPlanImages[plan.id] ? (
                    <img
                      src={plan.image_url}
                      alt=""
                      className="block max-h-[720px] w-full object-contain"
                      onError={() => {
                        setMissingPlanImages((current) => ({ ...current, [plan.id]: true }));
                        toast.error('This floor plan image is missing. Replace it to store a fresh copy in Blob.');
                      }}
                    />
                  ) : (
                    <div className="flex min-h-[480px] flex-col items-center justify-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-6 text-center text-amber-900">
                      <p className="text-sm font-semibold">Floor plan image is missing</p>
                      <p className="max-w-md text-sm">
                        The floor record exists, but the old image is no longer available on Vercel.
                        Click Replace floor plan to upload it again.
                      </p>
                    </div>
                  )}
                  {resources
                    .filter((resource) => resource.floor_plan_x != null && resource.floor_plan_y != null)
                    .map((resource) => {
                      const isAmenity = resource.type === 'amenity';
                      return (
                        <div
                          key={resource.id}
                          role="button"
                          tabIndex={0}
                          title={`${resource.name} - ${resource.zone}`}
                          onMouseDown={(event) => {
                            event.stopPropagation();
                            dragActiveRef.current = true;
                            setSelected(resource);
                            setDragging(resource.id);
                          }}
                          onMouseMove={(e) => dragging === resource.id && handleDrag(e, resource)}
                          onMouseUp={() => dragging === resource.id && handleDragEnd(resource)}
                          onMouseLeave={() => dragging === resource.id && handleDragEnd(resource)}
                          onClick={(event) => {
                            event.stopPropagation();
                            justDraggedRef.current = false;
                          }}
                          style={{
                            left: `${resource.floor_plan_x}%`,
                            top: `${resource.floor_plan_y}%`,
                          }}
                          className={
                            isAmenity
                              ? `absolute z-10 -translate-x-1/2 -translate-y-1/2 cursor-move rounded-md border border-slate-300 bg-white/95 px-2 py-1 text-xs font-semibold text-slate-800 shadow transition hover:scale-105 ${
                                  selected?.id === resource.id ? 'ring-4 ring-amber-300' : ''
                                }`
                              : `group absolute z-10 h-5 w-5 -translate-x-1/2 -translate-y-1/2 cursor-move rounded-full border-2 border-white shadow-md transition hover:scale-125 focus:outline-none focus:ring-4 ${
                                  selected?.id === resource.id
                                    ? 'bg-amber-400 ring-4 ring-amber-300'
                                    : 'bg-emerald-500 ring-2 ring-emerald-300 focus:ring-emerald-200'
                                }`
                          }
                          aria-label={`${resource.name} ${isAmenity ? 'label' : 'pin'}`}
                        >
                          {isAmenity ? resource.name : null}
                        </div>
                      );
                    })}
                </div>
              ) : (
                <div className="flex h-full items-center justify-center text-slate-400">
                  Upload a floor plan image to get started
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">
                {editingPlanId ? 'Edit Floor Plan' : 'Floor Plan Details'}
              </h3>
              {editingPlanId && (
                <button
                  type="button"
                  onClick={cancelEditingPlan}
                  className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
                >
                  <X size={14} />
                  Cancel
                </button>
              )}
            </div>

            <div className="mt-4 space-y-3">
              <input
                value={planForm.name}
                onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
                placeholder="Floor plan name"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={planForm.building}
                onChange={(e) => setPlanForm({ ...planForm, building: e.target.value })}
                placeholder="HQ location / building"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={planForm.floor}
                onChange={(e) => setPlanForm({ ...planForm, floor: e.target.value })}
                placeholder="Floor"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />

              {editingPlanId ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleSavePlanDetails}
                    disabled={savingPlan || !planForm.floor.trim()}
                    className="flex-1 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                  >
                    {savingPlan ? 'Saving...' : 'Save floor details'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeletePlan(plan)}
                    disabled={savingPlan || !plan}
                    className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 disabled:opacity-60"
                  >
                    Delete
                  </button>
                </div>
              ) : (
                <p className="text-xs text-slate-500">
                  Choose a floor plan from the list below or from the floor selector, then click
                  `Edit floor details` to rename the floor plan, floor, or building.
                </p>
              )}
            </div>
          </div>

          <div className="card p-4">
            <h3 className="text-sm font-semibold text-slate-900">Existing Floor Plans</h3>
            <div className="mt-3 space-y-2">
              {plans.length > 0 ? (
                plans.map((item) => (
                  <div
                    key={item.id}
                    className={`rounded-xl border px-3 py-3 ${
                      item.floor === floor
                        ? 'border-brand-300 bg-brand-50'
                        : 'border-slate-200'
                    }`}
                  >
                    <button
                    type="button"
                    onClick={() => {
                      setFloor(item.floor);
                      setEditingPlanId(null);
                      setSelectedPlanId(item.id);
                      setMessage('');
                    }}
                      className="w-full text-left"
                    >
                      <p className="text-sm font-medium text-slate-900">{item.name || `Floor ${item.floor}`}</p>
                      <p className="text-xs text-slate-500">{item.building}</p>
                    </button>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => startEditingPlan(item)}
                        className="inline-flex items-center gap-1 text-sm text-brand-600 hover:underline"
                      >
                        <Pencil size={14} />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeletePlan(item)}
                        className="inline-flex items-center gap-1 text-sm text-red-600 hover:underline"
                      >
                        <Trash2 size={14} />
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">No floor plans uploaded yet.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
