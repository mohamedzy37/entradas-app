import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { EventCardGrid } from '../components/EventCard';
import { ArrowRightIcon, ClockIcon, ShieldIcon, SparklesIcon, TicketIcon } from '../components/Icons';
import { SearchBar } from '../components/SearchBar';
import { EmptyState, ErrorState, Loading } from '../components/StateViews';
import { useAsync } from '../hooks/useAsync';
import { EVENT_TYPES, eventTypeEmoji, eventTypeLabel } from '../lib/constants';

export function HomePage() {
  const events = useAsync(() => api.listEvents({ limit: 8, sort: 'date_asc' }), []);
  const venues = useAsync(() => api.listVenues(), []);

  const cities = [...new Set((venues.data?.data ?? []).map((venue) => venue.city))].sort();

  return (
    <div>
      <section className="bg-brand text-white">
        <div className="mx-auto max-w-6xl px-4 pb-28 pt-12">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-xs font-semibold">
            <SparklesIcon width={14} height={14} /> Más de 10 eventos en toda España
          </span>
          <h1 className="mt-4 max-w-3xl text-3xl font-extrabold leading-tight sm:text-4xl lg:text-5xl">
            Tu próxima gran experiencia empieza con una entrada
          </h1>
          <p className="mt-3 max-w-2xl text-base text-white/85">
            Museos, partidos de fútbol, cines, festivales y conciertos. Encuentra el evento, elige tus
            entradas y resérvalas en segundos.
          </p>
          <div className="mt-5 flex flex-wrap gap-3 text-sm">
            <Link
              to="/eventos"
              className="rounded-md bg-cta px-4 py-2.5 font-bold text-brand-dark hover:bg-cta-dark"
            >
              Explorar eventos
            </Link>
            <Link
              to="/validar"
              className="rounded-md border border-white/40 px-4 py-2.5 font-semibold hover:bg-white/10"
            >
              Validar una entrada
            </Link>
          </div>
        </div>
      </section>

      <div className="mx-auto -mt-24 max-w-6xl px-4">
        <SearchBar cities={cities} />
      </div>

      <section className="mx-auto mt-10 max-w-6xl px-4">
        <h2 className="text-xl font-extrabold text-ink">Explora por categoría</h2>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {EVENT_TYPES.map((type) => (
            <Link
              key={type}
              to={`/eventos?type=${type}`}
              className="flex flex-col items-center gap-2 rounded-lg border border-line bg-white px-3 py-5 text-center transition hover:-translate-y-0.5 hover:border-sky hover:shadow-md"
            >
              <span className="text-3xl">{eventTypeEmoji(type)}</span>
              <span className="text-sm font-semibold text-ink">{eventTypeLabel(type)}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto mt-12 max-w-6xl px-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-extrabold text-ink">Eventos destacados</h2>
            <p className="text-sm text-muted">Los planes más próximos para no quedarte sin entradas.</p>
          </div>
          <Link to="/eventos" className="flex items-center gap-1 text-sm font-bold text-sky hover:underline">
            Ver todos <ArrowRightIcon width={16} height={16} />
          </Link>
        </div>

        <div className="mt-4">
          {events.loading ? (
            <Loading label="Cargando eventos..." />
          ) : events.error ? (
            <ErrorState error={events.error} onRetry={events.reload} />
          ) : (events.data?.data.length ?? 0) === 0 ? (
            <EmptyState title="Todavía no hay eventos" subtitle="Vuelve pronto para descubrir planes." />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {events.data?.data.map((event) => (
                <EventCardGrid key={event.id} event={event} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="mt-14 bg-white py-12">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="text-center text-xl font-extrabold text-ink">Por qué reservar con EntradasYa</h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-3">
            <Feature
              icon={<TicketIcon />}
              title="Entrada con código único"
              text="Cada entrada incluye un código XXXX-XXXX-XXXX para validarla en el acceso al evento."
            />
            <Feature
              icon={<ClockIcon />}
              title="Reserva sin pagar al instante"
              text="Guardamos tus entradas durante 15 minutos mientras completas el pago con total tranquilidad."
            />
            <Feature
              icon={<ShieldIcon />}
              title="Pago seguro (demo)"
              text="Proceso de pago simulado con confirmación inmediata. Sin cargos reales en tu tarjeta."
            />
          </div>
        </div>
      </section>

      <section className="mx-auto mt-12 max-w-6xl px-4">
        <div className="overflow-hidden rounded-xl bg-gradient-to-r from-brand to-sky p-8 text-white sm:p-10">
          <h3 className="max-w-xl text-2xl font-extrabold">¿Listo para tu próximo plan?</h3>
          <p className="mt-2 max-w-xl text-white/85">
            Filtra por ciudad, fecha y tipo de evento para encontrar la experiencia perfecta.
          </p>
          <Link
            to="/eventos"
            className="mt-5 inline-flex items-center gap-2 rounded-md bg-cta px-5 py-3 font-bold text-brand-dark hover:bg-cta-dark"
          >
            Buscar entradas <ArrowRightIcon width={18} height={18} />
          </Link>
        </div>
      </section>
    </div>
  );
}

function Feature({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-lg border border-line bg-white p-6 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-sky/10 text-sky">
        {icon}
      </div>
      <h3 className="mt-4 font-bold text-ink">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{text}</p>
    </div>
  );
}
