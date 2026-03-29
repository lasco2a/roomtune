import { type ReactNode } from 'react';

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-950 disabled:opacity-40 disabled:pointer-events-none';

const variants: Record<string, string> = {
  primary: 'bg-indigo-600 text-white hover:bg-indigo-500 focus:ring-indigo-500',
  secondary: 'bg-gray-800 text-gray-200 hover:bg-gray-700 focus:ring-gray-600',
  danger: 'bg-red-600/80 text-white hover:bg-red-500 focus:ring-red-500',
  ghost: 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60 focus:ring-gray-600',
};

const sizes: Record<string, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export function Button({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  disabled,
  className = '',
  type = 'button',
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {children}
    </button>
  );
}
