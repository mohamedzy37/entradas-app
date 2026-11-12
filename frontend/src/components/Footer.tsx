import { Link } from 'react-router-dom';
import { TicketIcon } from './Icons';

export function Footer() {
  return (
    <footer className="mt-16 bg-brand-dark text-white/80">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <div className="flex items-center gap-2 text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-cta text-brand-dark">
              <TicketIcon width={18} height={18} />
            </span>
            <span className="text-lg font-extrabold">EntradasYa</span>
          </div>
          <p className="mt-3 text-sm leading-relaxed">
            Entradas para museos, fútbol, cine, festivales y conciertos. Reserva en segundos y recibe
            tu entrada con código único.
          </p>
        </div>

        <div>
          <h4 className="mb-3 font-semibold text-white">Explorar</h4>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-white" to="/eventos">Todos los eventos</Link></li>
            <li><Link className="hover:text-white" to="/eventos?type=MUSEUM">Museos</Link></li>
            <li><Link className="hover:text-white" to="/eventos?type=FOOTBALL">Fútbol</Link></li>
            <li><Link className="hover:text-white" to="/eventos?type=FESTIVAL">Festivales</Link></li>
          </ul>
        </div>

        <div>
          <h4 className="mb-3 font-semibold text-white">Ayuda</h4>
          <ul className="space-y-2 text-sm">
            <li><Link className="hover:text-white" to="/validar">Validar una entrada</Link></li>
            <li><span className="cursor-default">Cómo funciona</span></li>
            <li><span className="cursor-default">Atención al cliente</span></li>
            <li><span className="cursor-default">Preguntas frecuentes</span></li>
          </ul>
        </div>

        <div>
          <h4 className="mb-3 font-semibold text-white">Legal</h4>
          <ul className="space-y-2 text-sm">
            <li><span className="cursor-default">Términos y condiciones</span></li>
            <li><span className="cursor-default">Privacidad</span></li>
            <li><span className="cursor-default">Cookies</span></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 py-5 text-center text-xs text-white/60">
        Demo de API de entradas · Pago simulado sin cargos reales · © {new Date().getFullYear()} EntradasYa
      </div>
    </footer>
  );
}
