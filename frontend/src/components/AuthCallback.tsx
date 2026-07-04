import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';

// ---------------------------------------------------------------------------
// AuthCallback – Receives the JWT from the backend OAuth redirect
// ---------------------------------------------------------------------------

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const { setToken } = useAuth();
  const navigate = useNavigate();
  const processed = useRef(false);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    'loading',
  );
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    // Guard against React StrictMode double-mount
    if (processed.current) return;
    processed.current = true;

    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setErrorMsg('No authentication token received from GitHub.');
      return;
    }

    (async () => {
      try {
        await setToken(token);
        setStatus('success');
        // Brief pause so the user can see the success state
        setTimeout(() => navigate('/dashboard', { replace: true }), 800);
      } catch {
        setStatus('error');
        setErrorMsg('Failed to authenticate. Please try again.');
      }
    })();
  }, [searchParams, setToken, navigate]);

  return (
    <div className="auth-callback-page">
      <div className="auth-callback-card">
        {status === 'loading' && (
          <>
            <Loader2 size={40} className="auth-callback-spinner" />
            <h2 className="auth-callback-title">Authenticating…</h2>
            <p className="auth-callback-desc">
              Connecting your GitHub account to Reflexion.
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle2 size={40} className="auth-callback-success-icon" />
            <h2 className="auth-callback-title">Welcome!</h2>
            <p className="auth-callback-desc">
              Redirecting you to the dashboard…
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={40} className="auth-callback-error-icon" />
            <h2 className="auth-callback-title">Authentication Failed</h2>
            <p className="auth-callback-desc">{errorMsg}</p>
            <button
              className="auth-callback-retry"
              onClick={() => navigate('/', { replace: true })}
            >
              Back to Login
            </button>
          </>
        )}
      </div>
    </div>
  );
}
