import { useEffect, useRef, type ReactNode } from 'react';
import { X, ArrowUpRight, Check, LoaderCircle, Sparkles, Inbox } from 'lucide-react';
export function Logo({ small = false }: { small?: boolean }) {
  return (
    <div className={`brand ${small ? 'small' : ''}`}>
      <span className="brand-symbol">
        <span />
        <span />
        <span />
        <span />
      </span>
      {!small && (
        <span>
          SmartHire<span className="brand-ai">AI</span>
        </span>
      )}
    </div>
  );
}
export function Avatar({ name, size = '', index = 0 }: { name: string; size?: string; index?: number }) {
  const n = name
    .split(' ')
    .map((n) => n[0])
    .slice(0, 2)
    .join('');
  return <span className={`avatar ${size} avatar-${index % 6}`}>{n}</span>;
}
export function Badge({ children, status = '' }: { children?: ReactNode; status?: string }) {
  return (
    <span className={`badge badge-${status.toLowerCase().replaceAll(' ', '-')}`}>
      <i />
      {children || status}
    </span>
  );
}
export function Match({ value }: { value: number }) {
  return (
    <span className={`match ${value >= 85 ? 'strong' : value >= 70 ? 'good' : 'fair'}`}>
      <Sparkles size={12} />
      {value}%
    </span>
  );
}
export function Modal({
  title,
  subtitle,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    ref.current?.focus();
    function handle(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Tab') {
        const els = ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input, select, textarea, a[href], [tabindex="0"]',
        );
        if (!els?.length) return;
        const first = els[0],
          last = els[els.length - 1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener('keydown', handle);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener('keydown', handle);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`modal ${wide ? 'modal-wide' : ''}`}
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <div className="modal-heading">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-btn" aria-label="Close dialog" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Empty({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Inbox size={27} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={25} />
      <span>Getting things ready…</span>
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function Metric({
  title,
  value,
  note,
  icon,
  points,
  green = false,
}: {
  title: string;
  value: string | number;
  note: string;
  icon: ReactNode;
  points: string;
  green?: boolean;
}) {
  return (
    <div className={`metric card ${green ? 'metric-highlight' : ''}`}>
      <div className="metric-label">
        {title}
        <span className="metric-icon">{icon}</span>
      </div>
      <div className="metric-number">
        {value}
        <svg width="101" height="42" viewBox="0 0 101 42" aria-hidden="true">
          <defs>
            <linearGradient id={`grad${title.replaceAll(' ', '')}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#269f70" stopOpacity=".18" />
              <stop offset="100%" stopColor="#269f70" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={`M0 42 L${points.replaceAll(' ', ' L')} L100 42 Z`}
            fill={`url(#grad${title.replaceAll(' ', '')})`}
          />
          <polyline
            points={points}
            fill="none"
            stroke="#329d77"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <div className="metric-note">
        <span>
          <ArrowUpRight size={13} />
          {note.split('|')[0]}
        </span>
        {note.split('|')[1]}
      </div>
    </div>
  );
}
export function CheckItem({ children }: { children: ReactNode }) {
  return (
    <div className="check-item">
      <Check size={15} />
      {children}
    </div>
  );
}
export function dateLabel(value: string) {
  return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
