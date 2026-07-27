import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

interface ButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  isLoading?: boolean;
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
  id?: string;
  type?: 'button' | 'submit' | 'reset';
}

export default function Button({
  children,
  variant = 'primary',
  isLoading = false,
  className = '',
  disabled,
  onClick,
  id,
  type = 'button',
}: ButtonProps) {
  let variantClass = '';
  if (variant === 'primary') {
    variantClass = 'bg-zinc-100 hover:bg-zinc-200 text-zinc-950';
  } else if (variant === 'secondary') {
    variantClass = 'bg-zinc-900 border border-zinc-800 text-zinc-100 hover:bg-zinc-800/80';
  } else if (variant === 'ghost') {
    variantClass = 'hover:bg-zinc-900 text-zinc-400 hover:text-zinc-100';
  } else if (variant === 'danger') {
    variantClass = 'bg-red-950/30 border border-red-900/50 text-red-400 hover:bg-red-900/40';
  }

  return (
    <motion.button
      whileHover={!disabled && !isLoading ? { scale: 1.01 } : {}}
      whileTap={!disabled && !isLoading ? { scale: 0.98 } : {}}
      className={`relative flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${variantClass} ${className}`}
      disabled={disabled || isLoading}
      onClick={onClick}
      id={id}
      type={type}
    >
      {isLoading ? (
        <span className="auth-loading-spinner" style={{ width: 14, height: 14 }} />
      ) : null}
      {children}
    </motion.button>
  );
}

interface IconButtonProps {
  icon: ReactNode;
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
}

export function IconButton({ icon, className = '', disabled, onClick }: IconButtonProps) {
  return (
    <motion.button
      whileHover={!disabled ? { scale: 1.05 } : {}}
      whileTap={!disabled ? { scale: 0.95 } : {}}
      className={`p-2 rounded-md hover:bg-zinc-900 text-zinc-400 hover:text-zinc-100 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {icon}
    </motion.button>
  );
}
