export default function AnimatedBackground() {
  return (
    <div className="animated-bg">
      {/* Film grain noise overlay */}
      <div className="noise-overlay" />

      {/* Large blurred atmospheric lighting sources */}
      <div className="bg-radial-glow bg-radial-glow--1" />
      <div className="bg-radial-glow bg-radial-glow--2" />

      {/* Subtle Constellation Graph connections drifting under */}
      <svg
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          opacity: 0.12,
        }}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <linearGradient id="line-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.1" />
          </linearGradient>
        </defs>

        {/* Slow drifting constellation dots & lines */}
        <g style={{ animation: 'drift 80s linear infinite' }}>
          {/* Node 1 */}
          <circle cx="20%" cy="30%" r="1.5" fill="#fafafa" />
          <circle cx="20%" cy="30%" r="5" stroke="#fafafa" strokeOpacity="0.15" strokeWidth="0.5" />
          
          {/* Node 2 */}
          <circle cx="45%" cy="20%" r="1.5" fill="#fafafa" />
          
          {/* Node 3 */}
          <circle cx="35%" cy="65%" r="1.5" fill="#fafafa" />
          
          {/* Connections */}
          <line x1="20%" y1="30%" x2="45%" y2="20%" stroke="url(#line-grad)" strokeWidth="0.5" />
          <line x1="20%" y1="30%" x2="35%" y2="65%" stroke="url(#line-grad)" strokeWidth="0.5" />
        </g>

        <g style={{ animation: 'drift-reverse 100s linear infinite' }}>
          {/* Node 4 */}
          <circle cx="75%" cy="40%" r="1.5" fill="#fafafa" />
          <circle cx="75%" cy="40%" r="5" stroke="#fafafa" strokeOpacity="0.15" strokeWidth="0.5" />
          
          {/* Node 5 */}
          <circle cx="60%" cy="75%" r="1.5" fill="#fafafa" />
          
          {/* Node 6 */}
          <circle cx="85%" cy="80%" r="1.5" fill="#fafafa" />
          
          {/* Connections */}
          <line x1="75%" y1="40%" x2="60%" y2="75%" stroke="url(#line-grad)" strokeWidth="0.5" />
          <line x1="75%" y1="40%" x2="85%" y2="80%" stroke="url(#line-grad)" strokeWidth="0.5" />
          <line x1="60%" y1="75%" x2="85%" y2="80%" stroke="url(#line-grad)" strokeWidth="0.5" />
        </g>
      </svg>

      <style>{`
        @keyframes drift {
          0% { transform: rotate(0deg) translate(0, 0); }
          50% { transform: rotate(2deg) translate(15px, -15px); }
          100% { transform: rotate(0deg) translate(0, 0); }
        }
        @keyframes drift-reverse {
          0% { transform: rotate(0deg) translate(0, 0); }
          50% { transform: rotate(-3deg) translate(-20px, 15px); }
          100% { transform: rotate(0deg) translate(0, 0); }
        }
      `}</style>
    </div>
  );
}
