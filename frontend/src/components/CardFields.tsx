import { CreditCardIcon } from './Icons';

export interface CardValues {
  cardNumber: string;
  cardHolder: string;
  expiryMonth: string;
  expiryYear: string;
  cvv: string;
}

export const EMPTY_CARD: CardValues = {
  cardNumber: '',
  cardHolder: '',
  expiryMonth: '',
  expiryYear: '',
  cvv: '',
};

export const VALID_TEST_CARD: CardValues = {
  cardNumber: '4242 4242 4242 4242',
  cardHolder: 'ANA GARCIA',
  expiryMonth: '12',
  expiryYear: String(new Date().getFullYear() + 1),
  cvv: '123',
};

export const DECLINED_TEST_CARD: CardValues = {
  cardNumber: '4000 0000 0000 0002',
  cardHolder: 'LUIS PEREZ',
  expiryMonth: '05',
  expiryYear: String(new Date().getFullYear() + 2),
  cvv: '999',
};

export function validateCard(values: CardValues): string | null {
  const digits = values.cardNumber.replace(/\s+/g, '');
  if (!/^\d{12,19}$/.test(digits)) return 'Número de tarjeta inválido (12-19 dígitos)';
  if (values.cardHolder.trim().length < 3) return 'Nombre del titular inválido';
  const month = Number(values.expiryMonth);
  if (!Number.isInteger(month) || month < 1 || month > 12) return 'Mes de caducidad inválido';
  const year = Number(values.expiryYear);
  if (!Number.isInteger(year) || year < new Date().getFullYear()) return 'Año de caducidad inválido';
  if (!/^\d{3,4}$/.test(values.cvv.trim())) return 'CVV inválido (3-4 dígitos)';
  return null;
}

interface CardFieldsProps {
  value: CardValues;
  onChange: (value: CardValues) => void;
}

export function CardFields({ value, onChange }: CardFieldsProps) {
  function set<K extends keyof CardValues>(key: K, next: CardValues[K]) {
    onChange({ ...value, [key]: next });
  }

  const inputClass =
    'w-full rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-sky focus:ring-2 focus:ring-sky/30';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onChange(VALID_TEST_CARD)}
          className="rounded-full border border-sky/30 bg-sky/5 px-3 py-1 text-xs font-semibold text-sky hover:bg-sky/10"
        >
          Rellenar tarjeta de prueba válida
        </button>
        <button
          type="button"
          onClick={() => onChange(DECLINED_TEST_CARD)}
          className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-600 hover:bg-red-100"
        >
          Probar tarjeta rechazada (…0002)
        </button>
      </div>

      <label className="block">
        <span className="mb-1 block text-sm font-semibold text-ink">Número de tarjeta</span>
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
            <CreditCardIcon width={18} height={18} />
          </span>
          <input
            value={value.cardNumber}
            onChange={(e) => set('cardNumber', e.target.value)}
            inputMode="numeric"
            placeholder="4242 4242 4242 4242"
            className={`${inputClass} pl-9`}
            autoComplete="cc-number"
          />
        </div>
      </label>

      <label className="block">
        <span className="mb-1 block text-sm font-semibold text-ink">Titular de la tarjeta</span>
        <input
          value={value.cardHolder}
          onChange={(e) => set('cardHolder', e.target.value.toUpperCase())}
          placeholder="NOMBRE APELLIDOS"
          className={inputClass}
          autoComplete="cc-name"
        />
      </label>

      <div className="grid grid-cols-3 gap-3">
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">Mes</span>
          <input
            value={value.expiryMonth}
            onChange={(e) => set('expiryMonth', e.target.value.replace(/\D/g, '').slice(0, 2))}
            placeholder="MM"
            inputMode="numeric"
            className={inputClass}
            autoComplete="cc-exp-month"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">Año</span>
          <input
            value={value.expiryYear}
            onChange={(e) => set('expiryYear', e.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="AAAA"
            inputMode="numeric"
            className={inputClass}
            autoComplete="cc-exp-year"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">CVV</span>
          <input
            value={value.cvv}
            onChange={(e) => set('cvv', e.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="123"
            inputMode="numeric"
            className={inputClass}
            autoComplete="cc-csc"
          />
        </label>
      </div>

      <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
        🔒 Pago <strong>simulado</strong>: no se realiza ningún cargo real. Solo para esta demo.
      </p>
    </div>
  );
}
