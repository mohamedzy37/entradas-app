import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { EVENT_TYPES, eventTypeLabel } from '../lib/constants';
import { CalendarIcon, MapPinIcon, SearchIcon, TicketIcon } from './Icons';

interface SearchBarProps {
  cities?: string[];
  variant?: 'hero' | 'compact';
  initial?: { q?: string; type?: string; city?: string; from?: string };
}

export function SearchBar({ cities = [], variant = 'hero', initial }: SearchBarProps) {
  const navigate = useNavigate();
  const [q, setQ] = useState(initial?.q ?? '');
  const [type, setType] = useState(initial?.type ?? '');
  const [city, setCity] = useState(initial?.city ?? '');
  const [from, setFrom] = useState(initial?.from?.slice(0, 10) ?? '');

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    if (type) params.set('type', type);
    if (city.trim()) params.set('city', city.trim());
    if (from) params.set('from', new Date(`${from}T00:00:00`).toISOString());
    navigate(`/eventos?${params.toString()}`);
  }

  const fieldClass =
    'w-full rounded-md border border-line bg-white px-3 py-3 text-sm text-ink outline-none focus:border-sky focus:ring-2 focus:ring-sky/30';

  return (
    <form
      onSubmit={handleSubmit}
      className={`rounded-lg border-[3px] border-cta bg-white shadow-lg ${
        variant === 'hero' ? 'p-2' : 'p-2'
      }`}
    >
      <div className="grid gap-2 md:grid-cols-12">
        <label className="relative md:col-span-4">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
            <SearchIcon width={18} height={18} />
          </span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className={`${fieldClass} pl-9`}
            placeholder="¿Qué quieres ver? Museo, partido, concierto..."
          />
        </label>

        <label className="relative md:col-span-3">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
            <TicketIcon width={18} height={18} />
          </span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className={`${fieldClass} appearance-none pl-9`}
          >
            <option value="">Cualquier tipo</option>
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {eventTypeLabel(t)}
              </option>
            ))}
          </select>
        </label>

        <label className="relative md:col-span-2">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
            <MapPinIcon width={18} height={18} />
          </span>
          <input
            value={city}
            onChange={(e) => setCity(e.target.value)}
            list="search-cities"
            className={`${fieldClass} pl-9`}
            placeholder="Ciudad"
          />
          <datalist id="search-cities">
            {cities.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>

        <label className="relative md:col-span-2">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
            <CalendarIcon width={18} height={18} />
          </span>
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className={`${fieldClass} pl-9`}
          />
        </label>

        <div className="md:col-span-1">
          <button
            type="submit"
            className="flex h-full w-full items-center justify-center gap-2 rounded-md bg-sky px-4 py-3 text-sm font-bold text-white transition hover:bg-sky-dark"
          >
            <SearchIcon width={18} height={18} />
            <span className="md:hidden">Buscar</span>
          </button>
        </div>
      </div>
    </form>
  );
}
