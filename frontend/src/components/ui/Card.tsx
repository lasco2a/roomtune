import { type ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  className?: string;
}

export function Card({ children, title, subtitle, className = '' }: CardProps) {
  return (
    <div className={`rounded-xl border border-gray-800 bg-gray-900/60 p-6 ${className}`}>
      {title && (
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-gray-100">{title}</h3>
          {subtitle && <p className="mt-1 text-sm text-gray-400">{subtitle}</p>}
        </div>
      )}
      {children}
    </div>
  );
}
