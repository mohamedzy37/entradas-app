import { useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { TicketLookup } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { AlertIcon, CheckIcon, MapPinIcon, TicketIcon } from '../components/Icons';
import { TICKET_STATUS_META } from '../lib/constants';
import { formatDateTime } from '../lib/format';

export function ValidatorPage() {
  const { hasRole } = useAuth();
  const canCheckIn = hasRole('ADMIN', 'MANAGER');
  const [code, setCode] = useState('');
  const [ticket, setTicket] = useState<TicketLookup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function normalize(value: string) {
    return value.trim().toUpperCase();
  }

  async function run(action: 'validate' | 'checkin') {
    const value = normalize(code);
    if (!value) {
      setError('Introduce el código de la entrada.');
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const response =
        action === 'validate' ? await api.getTicket(value) : await api.checkInTicket(value);
      setTicket(response.data);
      if (action === 'checkin') setMessage('Acceso registrado correctamente.');
    } catch (err) {
      setTicket(null);
      setError(err instanceof Error ? err.message : 'No se pudo validar la entrada.');
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void run('validate');
  }

  const statusMeta = ticket ? TICKET_STATUS_META[ticket.status] ?? TICKET_STATUS_META.VALID : null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-sky/10 text-sky">
          <TicketIcon />
        </span>
        <h1 className="mt-3 text-2xl font-extrabold text-ink">Validar una entrada</h1>
        <p className="mt-1 text-sm text-muted">
          Comprueba el estado de una entrada o registra el acceso en la puerta del evento.
        </p>
      </div>

      <form onSubmit={onSubmit} className="mt-6 rounded-xl border border-line bg-white p-5">
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">Código de la entrada</span>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="XXXX-XXXX-XXXX"
            className="w-full rounded-md border border-line px-3 py-3 font-mono text-lg tracking-wider outline-none focus:border-sky focus:ring-2 focus:ring-sky/30"
          />
        </label>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-sky px-4 py-3 font-bold text-white hover:bg-sky-dark disabled:bg-gray-300"
          >
            {loading ? 'Comprobando...' : 'Consultar estado'}
          </button>
          {canCheckIn ? (
            <button
              type="button"
              disabled={loading}
              onClick={() => void run('checkin')}
              className="rounded-md border border-green-600 px-4 py-3 font-bold text-green-700 hover:bg-green-50 disabled:opacity-50"
            >
              Registrar acceso
            </button>
          ) : null}
        </div>
        {!canCheckIn ? (
          <p className="mt-3 text-xs text-muted">
            Solo el personal con rol gestor o administrador puede registrar accesos. Inicia
            sesi&oacute;n con una de esas cuentas.
          </p>
        ) : null}
      </form>

      {error ? (
        <div className="mt-5 flex items-start gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertIcon width={18} height={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {message ? (
        <div className="mt-5 flex items-start gap-2 rounded-lg bg-green-50 px-4 py-3 text-sm font-semibold text-green-800">
          <CheckIcon width={18} height={18} className="mt-0.5 shrink-0" />
          <span>{message}</span>
        </div>
      ) : null}

      {ticket && statusMeta ? (
        <div className="mt-5 overflow-hidden rounded-xl border border-line bg-white">
          <div className="flex items-center justify-between border-b border-line bg-gray-50 px-5 py-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">Código</p>
              <p className="font-mono text-xl font-extrabold text-ink">{ticket.code}</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${statusMeta.className}`}>
              {statusMeta.label}
            </span>
          </div>
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <Detail label="Evento">{ticket.event.title}</Detail>
            <Detail label="Tipo de entrada">{ticket.ticketType.name}</Detail>
            <Detail label="Fecha">{formatDateTime(ticket.event.startAt)}</Detail>
            <Detail label="Lugar">
              <span className="flex items-center gap-1">
                <MapPinIcon width={14} height={14} /> {ticket.event.venue.name}, {ticket.event.venue.city}
              </span>
            </Detail>
            <Detail label="Pedido">{ticket.orderReference}</Detail>
            <Detail label="Titular">{ticket.holderName ?? '—'}</Detail>
            {ticket.usedAt ? <Detail label="Usada el">{formatDateTime(ticket.usedAt)}</Detail> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-ink">{children}</p>
    </div>
  );
}
