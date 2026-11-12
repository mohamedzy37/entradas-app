import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { EventType } from '../api/types';
import { EventCardRow } from '../components/EventCard';
import { Filters } from '../components/Filters';
import { Pagination } from '../components/Pagination';
import { SearchBar } from '../components/SearchBar';
import { EmptyState, ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { SORT_OPTIONS } from '../lib/constants';

export function EventsPage() {
  const [params, setParams] = useSearchParams();

  const q = params.get('q') ?? '';
  const type = params.get('type') ?? '';
  const city = params.get('city') ?? '';
  const from = params.get('from') ?? '';
  const sort = params.get('sort') ?? 'date_asc';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);

  const selectedTypes = type ? (type.split(',').filter(Boolean) as EventType[]) : [];

  const events = useAsync(
    () => api.listEvents({ q, type, city, from, sort, page, limit: 12 }),
    [q, type, city, from, sort, page],
  );
  const venues = useAsync(() => api.listVenues(), []);
  const cities = [...new Set((venues.data?.data ?? []).map((v) => v.city))].sort();

  function update(patch: Record<string, string | undefined>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (!value) next.delete(key);
      else next.set(key, value);
    }
    if (!('page' in patch)) next.delete('page');
    setParams(next, { replace: true });
  }

  function toggleType(t: EventType) {
    const set = new Set(selectedTypes);
    if (set.has(t)) set.delete(t);
    else set.add(t);
    update({ type: [...set].join(',') || undefined });
  }

  function clearFilters() {
    const next = new URLSearchParams();
    if (q) next.set('q', q);
    setParams(next, { replace: true });
  }

  const total = events.data?.pagination.total ?? 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <nav className="mb-3 text-sm text-muted">
        <Link to="/" className="text-sky hover:underline">
          Inicio
        </Link>{' '}
        <span>›</span> <span>Eventos</span>
      </nav>

      <SearchBar variant="compact" cities={cities} initial={{ q, type: selectedTypes[0], city, from }} />

      <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="lg:sticky lg:top-4 lg:self-start">
          <Filters
            selectedTypes={selectedTypes}
            city={city}
            from={from}
            cities={cities}
            onToggleType={toggleType}
            onCityChange={(value) => update({ city: value || undefined })}
            onFromChange={(value) => update({ from: value || undefined })}
            onClear={clearFilters}
          />
        </aside>

        <section>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-extrabold text-ink">
                {q ? `Resultados para “${q}”` : 'Todos los eventos'}
              </h1>
              <p className="text-sm text-muted">
                {events.loading ? 'Buscando...' : `${total} evento${total === 1 ? '' : 's'} encontrado${total === 1 ? '' : 's'}`}
              </p>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">Ordenar por</span>
              <select
                value={sort}
                onChange={(e) => update({ sort: e.target.value })}
                className="rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold outline-none focus:border-sky"
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-4 space-y-4">
            {events.loading ? (
              <Loading label="Cargando eventos..." />
            ) : events.error ? (
              <ErrorState error={events.error} onRetry={events.reload} />
            ) : (events.data?.data.length ?? 0) === 0 ? (
              <EmptyState
                title="No hay eventos con estos filtros"
                subtitle="Prueba a cambiar la ciudad, la fecha o el tipo de evento."
              />
            ) : (
              events.data?.data.map((event) => <EventCardRow key={event.id} event={event} />)
            )}
          </div>

          {events.data ? (
            <Pagination meta={events.data.pagination} onChange={(p) => update({ page: String(p) })} />
          ) : null}
        </section>
      </div>
    </div>
  );
}
