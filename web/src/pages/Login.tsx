import { useState } from 'react';
import { api, setSession } from '../lib/api';

export function Login({ onLogin }: { onLogin: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      if (mode === 'signup') {
        const u = await api.signup(email, password);
        if (u.status === 'pending') {
          setInfo('가입 완료. 관리자 승인 후 이용할 수 있습니다.');
          setMode('login');
          return;
        }
      }
      const res = await api.login(email, password);
      setSession(res.accessToken, res.role);
      onLogin();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <div className="auth__card">
        <div className="brand brand--lg">📍 SmartPlace Cloud</div>
        <p className="muted">네이버 스마트플레이스 통합 이미지 관리 자동화</p>

        <input placeholder="이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input
          type="password"
          placeholder="비밀번호 (8자 이상)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />
        {error && <p className="error">{error}</p>}
        {info && <p className="success">{info}</p>}
        <button className="btn btn--primary" onClick={submit} disabled={busy}>
          {busy ? '처리 중…' : mode === 'login' ? '로그인' : '회원가입'}
        </button>
        <button className="link" onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
          {mode === 'login' ? '계정이 없으신가요? 회원가입' : '로그인으로'}
        </button>
        <p className="hint">첫 가입자는 자동으로 관리자(승인됨)가 됩니다.</p>
      </div>
    </div>
  );
}
