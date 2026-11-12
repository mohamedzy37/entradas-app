import type { EventType } from '../api/types';
import { EVENT_TYPES, eventTypeEmoji, eventTypeLabel } from '../lib/constants';
import { FilterIcon } from './Icons';

interface FiltersProps {
  selectedTypes: EventType[];
  city: string;
  from: string;
  cities: string[];
  onToggleType: (type: EventType) => void;
  onCityChange: (city: string) => void;
  onFromChange: (from: string) => void;
  onClear: () => void;
}

export function Filters({
  selectedTypes,
  city,
  from,
  cities,
  onToggleType,
  onCityChange,
  onFromChange,
  onClear,
}: FiltersProps) {
  const hasFilters = selectedTypes.length > 0 || Boolean(city) || Boolean(from);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 font-bold text-ink">
          <FilterIcon width={18} height={18} /> Filtros
        </span>
        {hasFilters ? (
          <button onClick={onClear} className="text-sm font-semibold text-sky hover:underline">
            Limpiar
          </button>
        ) : null}
      </div>

      <div className="rounded-lg border border-line bg-white p-4">
        <h3 className="mb-3 text-sm font-bold text-ink">Tipo de evento</h3>
        <ul className="space-y-1.5">
          {EVENT_TYPES.map((type) => {
            const checked = selectedTypes.includes(type);
            return (
              <li key={type}>
                <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-gray-50">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleType(type)}
                    className="h-4 w-4 accent-sky"
                  />
                  <span>{eventTypeEmoji(type)}</span>
                  <span className={checked ? 'font-semibold text-ink' : 'text-muted'}>
                    {eventTypeLabel(type)}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="rounded-lg border border-line bg-white p-4">
        <h3 className="mb-3 text-sm font-bold text-ink">Ciudad</h3>
        <ul className="max-h-56 space-y-1.5 overflow-auto pr-1">
          <li>
            <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-gray-50">
              <input
                type="radio"
                name="city"
                checked={city === ''}
                onChange={() => onCityChange('')}
                className="h-4 w-4 accent-sky"
              />
              <span className={city === '' ? 'font-semibold' : 'text-muted'}>Todas las ciudades</span>
            </label>
          </li>
          {cities.map((c) => (
            <li key={c}>
              <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-gray-50">
                <input
                  type="radio"
                  name="city"
                  checked={city === c}
                  onChange={() => onCityChange(c)}
                  className="h-4 w-4 accent-sky"
                />
                <span className={city === c ? 'font-semibold' : 'text-muted'}>{c}</span>
              </label>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-line bg-white p-4">
        <h3 className="mb-3 text-sm font-bold text-ink">A partir de</h3>
        <input
          type="date"
          value={from ? from.slice(0, 10) : ''}
          onChange={(e) =>
            onFromChange(e.target.value ? new Date(`${e.target.value}T00:00:00`).toISOString() : '')
          }
          className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
        />
      </div>
    </div>
  );
}
