interface StatusChipProps {
  label: string;
  variant?: 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'accent';
}

export default function StatusChip({ label, variant = 'neutral' }: StatusChipProps) {
  let colorStyle = '';
  
  if (variant === 'success') {
    colorStyle = 'text-[#10b981] bg-[#10b981]/5 border-[#10b981]/10';
  } else if (variant === 'warning') {
    colorStyle = 'text-[#f59e0b] bg-[#f59e0b]/5 border-[#f59e0b]/10';
  } else if (variant === 'error') {
    colorStyle = 'text-[#ef4444] bg-[#ef4444]/5 border-[#ef4444]/10';
  } else if (variant === 'info') {
    colorStyle = 'text-[#06b6d4] bg-[#06b6d4]/5 border-[#06b6d4]/10';
  } else if (variant === 'neutral') {
    colorStyle = 'text-[#71717a] bg-zinc-900/50 border-zinc-800';
  } else if (variant === 'accent') {
    colorStyle = 'text-[#6366f1] bg-[#6366f1]/5 border-[#6366f1]/10';
  }

  return (
    <span className={`font-code text-xs px-2 py-0.5 border rounded ${colorStyle} select-none`}>
      {label}
    </span>
  );
}
