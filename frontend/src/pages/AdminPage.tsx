import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, type EventInput, type TicketTypeInput } from '../api/client';
import type {
  AdminStats,
  EventDetail,
  EventSummary,
  EventType,
  Order,
  Role,
  User,
  Venue,
} from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { AlertIcon, CheckIcon, TicketIcon } from '../components/Icons';
import { EmptyState, ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { EVENT_TYPES, eventTypeLabel, ORDER_STATUS_META } from '../lib/constants';
import { formatCents, formatDateTime } from '../lib/format';

type Tab = 'resumen' | 'pedidos' | 'eventos' | 'usuarios';

export function AdminPage() {
  const { user, hasRole } = useAuth();
  const isAdmin = hasRole('ADMIN');
  const [tab, setTab] = useState<Tab>('resumen');

  const tabs: Array<{ id: Tab; label: string }> = [
    { id: 'resumen', label: 'Resumen' },
    { id: 'pedidos', label: 'Pedidos' },
    { id: 'eventos', label: 'Eventos' },
    ...(isAdmin ? [{ id: 'usuarios' as Tab, label: 'Usuarios' }] : []),
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-ink">Panel de gesti&oacute;n</h1>
          <p className="text-sm text-muted">
            {user?.name} &middot;{" "}
            <span className="font-semibold text-ink">{user?.role}</span>
          </p>
        </div>
        <Link to="/eventos" className="text-sm font-semibold text-sky hover:underline">
          Ver cat&aacute;logo &rarr;
        </Link>
      </div>

      <div className="mt-5 flex flex-wrap gap-2 border-b border-line">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold transition ${
              tab === item.id
                ? 'border-sky text-sky'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === 'resumen' ? <SummaryTab /> : null}
        {tab === 'pedidos' ? <OrdersTab /> : null}
        {tab === 'eventos' ? <EventsTab /> : null}
        {tab === 'usuarios' && isAdmin ? <UsersTab /> : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resumen
// ---------------------------------------------------------------------------

function SummaryTab() {
  const stats = useAsync(() => api.adminStats(), []);

  if (stats.loading) return <Loading label="Calculando estad\u00edsticas..." />;
  if (stats.error) return <ErrorState error={stats.error} onRetry={stats.reload} />;
  if (!stats.data) return null;

  const data: AdminStats = stats.data.data;
  const cards: Array<{ label: string; value: string; hint?: string }> = [
    { label: 'Ingresos (pagados)', value: formatCents(data.revenueCents) },
    { label: 'Pedidos', value: String(data.orders), hint: `${data.paidOrders} pagados` },
    { label: 'Pendientes de pago', value: String(data.pendingOrders) },
    { label: 'Eventos publicados', value: String(data.publishedEvents), hint: `${data.events} en total` },
    { label: 'Entradas emitidas', value: String(data.tickets), hint: `${data.ticketsUsed} usadas` },
    { label: 'Usuarios', value: String(data.users) },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {cards.map((card) => (
        <div key={card.label} className="rounded-xl border border-line bg-white p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{card.label}</p>
          <p className="mt-2 text-3xl font-extrabold text-ink">{card.value}</p>
          {card.hint ? <p className="mt-1 text-xs text-muted">{card.hint}</p> : null}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pedidos
// ---------------------------------------------------------------------------

function OrdersTab() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const orders = useAsync(
    () => api.adminOrders({ q: query || undefined, status: status || undefined, page, limit: 20 }),
    [query, status, page],
  );

  return (
    <div>
      <form
        className="flex flex-wrap gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          orders.reload();
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por referencia o email"
          className="flex-1 rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
        >
          <option value="">Todos los estados</option>
          {Object.keys(ORDER_STATUS_META).map((key) => (
            <option key={key} value={key}>
              {ORDER_STATUS_META[key].label}
            </option>
          ))}
        </select>
      </form>

      {orders.loading ? <Loading label="Cargando pedidos..." /> : null}
      {orders.error ? <ErrorState error={orders.error} onRetry={orders.reload} /> : null}

      {orders.data && orders.data.data.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="No hay pedidos" subtitle="Prueba a cambiar los filtros." />
        </div>
      ) : null}

      {orders.data && orders.data.data.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-xl border border-line bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Referencia</th>
                <th className="px-4 py-3">Comprador</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Fecha</th>
                <th className="px-4 py-3 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.data.map((order: Order) => {
                const meta = ORDER_STATUS_META[order.status] ?? {
                  label: order.status,
                  className: 'bg-gray-100 text-gray-700',
                };
                return (
                  <tr key={order.id} className="border-t border-line">
                    <td className="px-4 py-3 font-mono font-semibold text-ink">
                      <Link to={`/pedido/${order.reference}`} className="hover:text-sky">
                        {order.reference}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className="block text-ink">{order.buyer.name}</span>
                      <span className="text-xs text-muted">{order.buyer.email}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${meta.className}`}>
                        {meta.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted">{formatDateTime(order.createdAt)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-ink">{order.total}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {orders.data && orders.data.pagination.totalPages > 1 ? (
        <Pager pagination={orders.data.pagination} onChange={setPage} />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Eventos (listado + edicion + tipos de entrada)
// ---------------------------------------------------------------------------

function EventsTab() {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<EventDetail | null>(null);
  const [creating, setCreating] = useState(false);
  const events = useAsync(
    () =>
      api.listEvents({
        q: query || undefined,
        limit: 50,
        sort: 'date_asc',
        includePast: true,
      }),
    [query],
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <div>
        <div className="flex items-center justify-between gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar evento"
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
          <button
            type="button"
            onClick={() => {
              setSelected(null);
              setCreating(true);
            }}
            className="whitespace-nowrap rounded-md bg-sky px-3 py-2 text-sm font-bold text-white hover:bg-sky-dark"
          >
            Nuevo
          </button>
        </div>

        {events.loading ? <Loading label="Cargando eventos..." /> : null}
        {events.error ? <ErrorState error={events.error} onRetry={events.reload} /> : null}

        <ul className="mt-3 max-h-[70vh] space-y-1 overflow-y-auto">
          {(events.data?.data ?? []).map((event: EventSummary) => (
            <li key={event.id}>
              <button
                type="button"
                onClick={() => void openEvent(event.id, setSelected, setCreating)}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition ${
                  selected?.id === event.id
                    ? 'border-sky bg-sky/5'
                    : 'border-line bg-white hover:border-sky'
                }`}
              >
                <span className="block font-semibold text-ink">{event.title}</span>
                <span className="text-xs text-muted">
                  {formatDateTime(event.startAt)} · {event.status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div>
        {creating ? (
          <EventForm
            onDone={() => {
              setCreating(false);
              events.reload();
            }}
            onCancel={() => setCreating(false)}
          />
        ) : selected ? (
          <EventDetailPanel
            event={selected}
            onRefresh={async () => {
              const fresh = await api.getEvent(selected.id);
              setSelected(fresh.data);
              events.reload();
            }}
            onDeleted={() => {
              setSelected(null);
              events.reload();
            }}
          />
        ) : (
          <EmptyState title="Selecciona un evento" subtitle="O crea uno nuevo con el bot\u00f3n 'Nuevo'." />
        )}
      </div>
    </div>
  );
}

async function openEvent(
  id: string,
  setSelected: (event: EventDetail) => void,
  setCreating: (value: boolean) => void,
) {
  setCreating(false);
  const response = await api.getEvent(id);
  setSelected(response.data);
}

function EventDetailPanel({
  event,
  onRefresh,
  onDeleted,
}: {
  event: EventDetail;
  onRefresh: () => Promise<void>;
  onDeleted: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (!window.confirm(`\u00bfEliminar el evento "${event.title}"?`)) return;
    setError(null);
    try {
      await api.adminDeleteEvent(event.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar.');
    }
  }

  if (editing) {
    return (
      <EventForm
        event={event}
        onDone={() => {
          setEditing(false);
          void onRefresh();
        }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <div className="rounded-xl border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-ink">{event.title}</h2>
          <p className="text-sm text-muted">
            {eventTypeLabel(event.type)} · {event.venue.name}, {event.venue.city}
          </p>
          <p className="mt-1 text-sm text-muted">{formatDateTime(event.startAt)}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded-md border border-line px-3 py-2 text-sm font-semibold hover:border-sky hover:text-sky"
          >
            Editar
          </button>
          <button
            type="button"
            onClick={() => void handleDelete()}
            className="rounded-md border border-red-300 px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50"
          >
            Eliminar
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertIcon width={16} height={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="mt-5 border-t border-line pt-4">
        <h3 className="flex items-center gap-2 text-sm font-extrabold text-ink">
          <TicketIcon width={16} height={16} className="text-sky" /> Tipos de entrada
        </h3>
        <TicketTypesManager event={event} onRefresh={onRefresh} />
      </div>
    </div>
  );
}

function TicketTypesManager({ event, onRefresh }: { event: EventDetail; onRefresh: () => Promise<void> }) {
  const [name, setName] = useState('');
  const [price, setPrice] = useState('');
  const [total, setTotal] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function addTicketType(event2: FormEvent) {
    event2.preventDefault();
    setError(null);
    const priceCents = Math.round(Number(price.replace(',', '.')) * 100);
    const quantityTotal = Number(total);
    if (!name.trim() || !Number.isFinite(priceCents) || priceCents < 0) {
      setError('Indica un nombre y un precio v\u00e1lido.');
      return;
    }
    if (!Number.isInteger(quantityTotal) || quantityTotal < 1) {
      setError('El aforo debe ser un entero mayor que 0.');
      return;
    }
    const payload: TicketTypeInput = {
      name: name.trim(),
      priceCents,
      quantityTotal,
      maxPerOrder: 10,
    };
    try {
      await api.adminCreateTicketType(event.id, payload);
      setName('');
      setPrice('');
      setTotal('');
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el tipo de entrada.');
    }
  }

  async function removeTicketType(id: string) {
    setError(null);
    try {
      await api.adminDeleteTicketType(id);
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar.');
    }
  }

  async function toggleActive(id: string, isActive: boolean) {
    setError(null);
    try {
      await api.adminUpdateTicketType(id, { isActive });
      await onRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo actualizar.');
    }
  }

  return (
    <div className="mt-3">
      <ul className="divide-y divide-line">
        {event.ticketTypes.map((tt) => (
          <li key={tt.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
            <div>
              <span className="font-semibold text-ink">{tt.name}</span>
              <span className="ml-2 text-muted">
                {tt.price} · {tt.quantitySold}/{tt.quantityTotal} vendidas · m&aacute;x {tt.maxPerOrder}
              </span>
              {tt.isActive === false ? (
                <span className="ml-2 rounded bg-gray-200 px-2 py-0.5 text-xs font-bold text-gray-700">
                  Inactivo
                </span>
              ) : null}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void toggleActive(tt.id, tt.isActive === false)}
                className="rounded border border-line px-2 py-1 text-xs font-semibold hover:border-sky hover:text-sky"
              >
                {tt.isActive === false ? 'Activar' : 'Desactivar'}
              </button>
              <button
                type="button"
                onClick={() => void removeTicketType(tt.id)}
                className="rounded border border-red-300 px-2 py-1 text-xs font-semibold text-red-600 hover:bg-red-50"
              >
                Eliminar
              </button>
            </div>
          </li>
        ))}
        {event.ticketTypes.length === 0 ? (
          <li className="py-3 text-sm text-muted">Este evento no tiene tipos de entrada.</li>
        ) : null}
      </ul>

      <form onSubmit={addTicketType} className="mt-3 flex flex-wrap items-end gap-2">
        <label className="flex-1">
          <span className="mb-1 block text-xs font-semibold text-muted">Nombre</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Entrada general"
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </label>
        <label className="w-24">
          <span className="mb-1 block text-xs font-semibold text-muted">Precio &euro;</span>
          <input
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="20"
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </label>
        <label className="w-24">
          <span className="mb-1 block text-xs font-semibold text-muted">Aforo</span>
          <input
            value={total}
            onChange={(e) => setTotal(e.target.value)}
            placeholder="100"
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </label>
        <button
          type="submit"
          className="rounded-md bg-sky px-4 py-2 text-sm font-bold text-white hover:bg-sky-dark"
        >
          A&ntilde;adir
        </button>
      </form>

      {error ? (
        <div className="mt-2 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertIcon width={16} height={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}
    </div>
  );
}

function EventForm({
  event,
  onDone,
  onCancel,
}: {
  event?: EventDetail;
  onDone: () => void;
  onCancel: () => void;
}) {
  const venues = useAsync(() => api.listVenues(), []);
  const [title, setTitle] = useState(event?.title ?? '');
  const [type, setType] = useState<EventType>(event?.type ?? 'OTHER');
  const [venueId, setVenueId] = useState(event?.venue.id ?? '');
  const [startAt, setStartAt] = useState(toLocalInput(event?.startAt));
  const [endAt, setEndAt] = useState(toLocalInput(event?.endAt ?? undefined));
  const [status, setStatus] = useState(event?.status ?? 'PUBLISHED');
  const [description, setDescription] = useState(event?.description ?? '');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(formEvent: FormEvent) {
    formEvent.preventDefault();
    setError(null);
    if (!title.trim() || !venueId || !startAt) {
      setError('Título, recinto y fecha de inicio son obligatorios.');
      return;
    }
    const payload: EventInput = {
      title: title.trim(),
      type,
      venueId,
      startAt: new Date(startAt).toISOString(),
      endAt: endAt ? new Date(endAt).toISOString() : null,
      status: status as EventInput['status'],
      description: description.trim() || null,
    };
    setSaving(true);
    try {
      if (event) await api.adminUpdateEvent(event.id, payload);
      else await api.adminCreateEvent(payload);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo guardar.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-line bg-white p-5">
      <h2 className="text-lg font-extrabold text-ink">
        {event ? 'Editar evento' : 'Nuevo evento'}
      </h2>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field label="Título" className="sm:col-span-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </Field>

        <Field label="Tipo">
          <select
            value={type}
            onChange={(e) => setType(e.target.value as EventType)}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          >
            {EVENT_TYPES.map((option) => (
              <option key={option} value={option}>
                {eventTypeLabel(option)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Estado">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          >
            {['DRAFT', 'PUBLISHED', 'SOLD_OUT', 'CANCELLED', 'FINISHED'].map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Recinto">
          <select
            value={venueId}
            onChange={(e) => setVenueId(e.target.value)}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          >
            <option value="">Selecciona un recinto</option>
            {(venues.data?.data ?? []).map((venue: Venue) => (
              <option key={venue.id} value={venue.id}>
                {venue.name} — {venue.city}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Inicio">
          <input
            type="datetime-local"
            value={startAt}
            onChange={(e) => setStartAt(e.target.value)}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </Field>

        <Field label="Fin (opcional)">
          <input
            type="datetime-local"
            value={endAt}
            onChange={(e) => setEndAt(e.target.value)}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </Field>

        <Field label="Descripción" className="sm:col-span-2">
          <textarea
            value={description ?? ''}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
          />
        </Field>
      </div>

      {error ? (
        <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertIcon width={16} height={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-sky px-5 py-2 font-bold text-white hover:bg-sky-dark disabled:bg-gray-300"
        >
          {saving ? 'Guardando...' : 'Guardar'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-line px-5 py-2 font-semibold hover:border-sky hover:text-sky"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Usuarios (solo ADMIN)
// ---------------------------------------------------------------------------

function UsersTab() {
  const { user: current } = useAuth();
  const [query, setQuery] = useState('');
  const [role, setRole] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const users = useAsync(
    () => api.adminUsers({ q: query || undefined, role: role || undefined, page, limit: 20 }),
    [query, role, page],
  );

  async function changeRole(id: string, newRole: Role) {
    setError(null);
    try {
      await api.adminUpdateRole(id, newRole);
      users.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cambiar el rol.');
    }
  }

  async function toggleActive(id: string, isActive: boolean) {
    setError(null);
    try {
      await api.adminUpdateActive(id, isActive);
      users.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cambiar el estado.');
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-3">
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar por nombre o email"
          className="flex-1 rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
        />
        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setPage(1);
          }}
          className="rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-sky"
        >
          <option value="">Todos los roles</option>
          <option value="ADMIN">ADMIN</option>
          <option value="MANAGER">MANAGER</option>
          <option value="CLIENT">CLIENT</option>
        </select>
      </div>

      {error ? (
        <div className="mt-3 flex items-start gap-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertIcon width={16} height={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {users.loading ? <Loading label="Cargando usuarios..." /> : null}
      {users.error ? <ErrorState error={users.error} onRetry={users.reload} /> : null}

      {users.data && users.data.data.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-xl border border-line bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Usuario</th>
                <th className="px-4 py-3">Rol</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Alta</th>
              </tr>
            </thead>
            <tbody>
              {users.data.data.map((item: User) => {
                const isSelf = item.id === current?.id;
                return (
                  <tr key={item.id} className="border-t border-line">
                    <td className="px-4 py-3">
                      <span className="block text-ink">{item.name}</span>
                      <span className="text-xs text-muted">{item.email}</span>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={item.role}
                        onChange={(e) => void changeRole(item.id, e.target.value as Role)}
                        className="rounded-md border border-line px-2 py-1 text-sm outline-none focus:border-sky"
                      >
                        <option value="CLIENT">CLIENT</option>
                        <option value="MANAGER">MANAGER</option>
                        <option value="ADMIN">ADMIN</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      {item.isActive ? (
                        <span className="inline-flex items-center gap-1 text-green-700">
                          <CheckIcon width={14} height={14} /> Activo
                        </span>
                      ) : (
                        <span className="text-red-600">Desactivado</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        disabled={isSelf}
                        onClick={() => void toggleActive(item.id, !item.isActive)}
                        className="rounded border border-line px-2 py-1 text-xs font-semibold hover:border-sky hover:text-sky disabled:opacity-40"
                      >
                        {item.isActive ? 'Desactivar' : 'Activar'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {users.data && users.data.pagination.totalPages > 1 ? (
        <Pager pagination={users.data.pagination} onChange={setPage} />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utilidades de UI
// ---------------------------------------------------------------------------

function Pager({
  pagination,
  onChange,
}: {
  pagination: { page: number; totalPages: number };
  onChange: (page: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-center gap-3 text-sm">
      <button
        type="button"
        disabled={pagination.page <= 1}
        onClick={() => onChange(pagination.page - 1)}
        className="rounded-md border border-line px-3 py-1.5 font-semibold disabled:opacity-40"
      >
        Anterior
      </button>
      <span className="text-muted">
        P&aacute;gina {pagination.page} de {pagination.totalPages}
      </span>
      <button
        type="button"
        disabled={pagination.page >= pagination.totalPages}
        onClick={() => onChange(pagination.page + 1)}
        className="rounded-md border border-line px-3 py-1.5 font-semibold disabled:opacity-40"
      >
        Siguiente
      </button>
    </div>
  );
}

function Field({
  label,
  className = '',
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-semibold text-muted">{label}</span>
      {children}
    </label>
  );
}

/** Convierte un ISO a valor de <input type="datetime-local">. */
function toLocalInput(iso?: string): string {
  if (!iso) return '';
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}
