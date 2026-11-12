import type { Pagination as PaginationMeta } from '../api/types';
import { ChevronLeftIcon, ChevronRightIcon } from './Icons';

interface PaginationProps {
  meta: PaginationMeta;
  onChange: (page: number) => void;
}

export function Pagination({ meta, onChange }: PaginationProps) {
  if (meta.totalPages <= 1) return null;

  const pages: number[] = [];
  const start = Math.max(1, meta.page - 2);
  const end = Math.min(meta.totalPages, start + 4);
  for (let p = start; p <= end; p += 1) pages.push(p);

  const buttonBase =
    'flex h-9 min-w-9 items-center justify-center rounded-md border px-2 text-sm font-semibold transition';

  return (
    <nav className="flex items-center justify-center gap-1 pt-6" aria-label="Paginación">
      <button
        className={`${buttonBase} border-line bg-white text-ink hover:border-sky disabled:opacity-40`}
        disabled={!meta.hasPrev}
        onClick={() => onChange(meta.page - 1)}
        aria-label="Página anterior"
      >
        <ChevronLeftIcon width={16} height={16} />
      </button>

      {start > 1 ? <span className="px-1 text-muted">…</span> : null}

      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`${buttonBase} ${
            p === meta.page
              ? 'border-sky bg-sky text-white'
              : 'border-line bg-white text-ink hover:border-sky'
          }`}
          aria-current={p === meta.page ? 'page' : undefined}
        >
          {p}
        </button>
      ))}

      {end < meta.totalPages ? <span className="px-1 text-muted">…</span> : null}

      <button
        className={`${buttonBase} border-line bg-white text-ink hover:border-sky disabled:opacity-40`}
        disabled={!meta.hasNext}
        onClick={() => onChange(meta.page + 1)}
        aria-label="Página siguiente"
      >
        <ChevronRightIcon width={16} height={16} />
      </button>
    </nav>
  );
}
