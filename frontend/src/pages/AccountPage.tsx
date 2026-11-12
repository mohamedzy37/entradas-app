import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Order } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { ChevronRightIcon, TicketIcon, UserIcon } from '../components/Icons';
import { ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { ORDER_STATUS_META } from '../lib/constants';
import { formatDateTime } from '../lib/format';

export function AccountPage() {
  const { user } = useAuth();
  const orders = useAsync(() => api.listMyOrders(), []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="flex items-center gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-sky/10 text-sky">
          <UserIcon />
        </span>
        <div>
          <h1 className="text-2xl font-extrabold text-ink">{user?.name}</h1>
          <p className="text-sm text-muted">{user?.email}</p>
        </div>
      </div>

      <h2 className="mt-8 flex items-center gap-2 text-lg font-extrabold text-ink">
        <TicketIcon width={20} height={20} className="text-sky" /> Mis entradas
      </h2>

      {orders.loading ? <Loading label="Cargando tus entradas..." /> : null}

      {orders.error ? (
        <div className="mt-4">
          <ErrorState error={orders.error} onRetry={orders.reload} />
        </div>
      ) : null}

      {orders.data && orders.data.data.length === 0 ? (
        <div className="mt-4 rounded-xl border border-line bg-white p-8 text-center">
          <p className="text-sm text-muted">Todavía no tienes ninguna reserva.</p>
          <Link
            to="/eventos"
            className="mt-4 inline-block rounded-md bg-sky px-5 py-3 font-bold text-white hover:bg-sky-dark"
          >
            Explorar eventos
          </Link>
        </div>
      ) : null}

      <div className="mt-4 space-y-4">
        {(orders.data?.data ?? []).map((order) => (
          <OrderCard key={order.id} order={order} />
        ))}
      </div>
    </div>
  );
}

function OrderCard({ order }: { order: Order }) {
  const statusMeta = ORDER_STATUS_META[order.status] ?? {
    label: order.status,
    className: 'bg-gray-100 text-gray-700',
  };

  return (
    <Link
      to={`/pedido/${order.reference}`}
      className="block rounded-xl border border-line bg-white p-5 transition hover:border-sky hover:shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-bold text-ink">{order.reference}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${statusMeta.className}`}>
            {statusMeta.label}
          </span>
        </div>
        <span className="text-xs text-muted">{formatDateTime(order.createdAt)}</span>
      </div>

      <ul className="mt-3 space-y-1">
        {order.items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-3 text-sm">
            <span className="text-ink">
              {item.quantity} × {item.eventTitle} — <span className="text-muted">{item.ticketTypeName}</span>
            </span>
            <span className="font-semibold text-ink">{item.subtotal}</span>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
        <span className="text-sm text-muted">
          Total <span className="font-extrabold text-ink">{order.total}</span>
        </span>
        <span className="flex items-center gap-1 text-sm font-semibold text-sky">
          Ver detalle <ChevronRightIcon width={16} height={16} />
        </span>
      </div>
    </Link>
  );
}
