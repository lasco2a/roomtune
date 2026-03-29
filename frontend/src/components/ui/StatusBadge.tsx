interface StatusBadgeProps {
  status: 'ok' | 'error' | 'warn' | 'pending' | 'running';
  label: string;
}

const colors: Record<string, string> = {
  ok: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  warn: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  pending: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  running: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
};

const dotColors: Record<string, string> = {
  ok: 'bg-emerald-400',
  error: 'bg-red-400',
  warn: 'bg-amber-400',
  pending: 'bg-gray-400',
  running: 'animate-pulse bg-amber-400',
};

export function StatusBadge({ status, label }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${colors[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColors[status]}`} />
      {label}
    </span>
  );
}
