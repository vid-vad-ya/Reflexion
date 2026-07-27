interface LogoProps {
  size?: number;
  className?: string;
}

export default function Logo({ size = 32, className = '' }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* 
        Geometric mark representing recursive iteration and feedback loops.
        Constructed using overlapping, layered tracks with subtle gradients.
      */}
      <defs>
        <linearGradient id="logo-grad-indigo" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#4f46e5" />
        </linearGradient>
        <linearGradient id="logo-grad-cyan" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#0891b2" />
        </linearGradient>
        <linearGradient id="logo-grad-base" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#1e1b4b" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#312e81" stopOpacity="0.4" />
        </linearGradient>
      </defs>

      {/* Main Base Path: Isometric recursive track */}
      <path
        d="M 50 12 L 85 32 L 85 68 L 50 88 L 15 68 L 15 32 Z"
        fill="url(#logo-grad-base)"
        stroke="rgba(255, 255, 255, 0.05)"
        strokeWidth="1.5"
      />

      {/* Inner loop/spiral: continuous execution cycle */}
      <path
        d="M 50 25 L 73 38 L 73 62 L 50 75 L 27 62 L 27 38 L 50 25 Z"
        stroke="rgba(255, 255, 255, 0.1)"
        strokeWidth="2"
        strokeDasharray="4 4"
      />

      {/* Primary Highlight Loop Ribbon (Indigo) */}
      <path
        d="M 50 12 L 85 32 L 85 50 L 50 30 L 27 43 L 50 56 L 73 43"
        stroke="url(#logo-grad-indigo)"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Self-Correction Loop Highlight (Cyan) */}
      <path
        d="M 50 88 L 15 68 L 15 50 L 50 70 L 73 57 L 50 44 L 27 57"
        stroke="url(#logo-grad-cyan)"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Core Node: The Reflexion nucleus */}
      <circle cx="50" cy="50" r="4.5" fill="#ffffff" />
      <circle cx="50" cy="50" r="9" stroke="#ffffff" strokeOpacity="0.3" strokeWidth="1" />
    </svg>
  );
}
