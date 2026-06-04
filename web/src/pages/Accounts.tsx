import { useEffect, useState } from 'react';
import { api, type NaverAccount, type Place } from '../lib/api';

export function Accounts() {
  const [accounts, setAccounts] = useState<NaverAccount[]>([]);
  const [places, setPlaces] = useState<Place[]>([]);
  const [alias, setAlias] = useState('');
  const [loginId, setLoginId] = useState('');
  const [loginPw, setLoginPw] = useState('');
  const [error, setError] = useState<string | null>(null);

  // place form
  const [accountId, setAccountId] = useState<number | ''>('');
  const [placeId, setPlaceId] = useState('');
  const [bizName, setBizName] = useState('');

  async function refresh() {
    setAccounts(await api.listAccounts());
    setPlaces(await api.listPlaces());
  }
  useEffect(() => {
    refresh().catch((e) => setError(String(e.message ?? e)));
  }, []);

  async function link() {
    setError(null);
    try {
      await api.linkAccount({ alias, loginId, loginPw });
      setAlias('');
      setLoginId('');
      setLoginPw('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function addPlace() {
    setError(null);
    try {
      await api.createPlace(Number(accountId), placeId, bizName);
      setPlaceId('');
      setBizName('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="grid2">
      <section className="card">
        <h2>네이버 계정 연동</h2>
        <p className="muted">
          아이디·비밀번호는 서버에서 <b>AES-256</b>으로 암호화 저장되며, 게이트웨이에서만 복호화해
          로그인에 사용합니다.
        </p>
        <input placeholder="별칭 (예: 프랜차이즈 본점)" value={alias} onChange={(e) => setAlias(e.target.value)} />
        <input placeholder="네이버 아이디" value={loginId} onChange={(e) => setLoginId(e.target.value)} autoComplete="off" />
        <input
          type="password"
          placeholder="네이버 비밀번호"
          value={loginPw}
          onChange={(e) => setLoginPw(e.target.value)}
          autoComplete="new-password"
        />
        <button className="btn btn--primary" onClick={link} disabled={!alias || !loginId || !loginPw}>
          계정 연동
        </button>
        {error && <p className="error">{error}</p>}

        <h3>연동된 계정</h3>
        <ul className="list">
          {accounts.map((a) => (
            <li key={a.id}>
              <b>{a.alias}</b> <span className="muted">#{a.id} · {a.status}</span>
            </li>
          ))}
          {!accounts.length && <li className="muted">아직 없음</li>}
        </ul>
      </section>

      <section className="card">
        <h2>가맹점 등록</h2>
        <select value={accountId} onChange={(e) => setAccountId(Number(e.target.value))}>
          <option value="">계정 선택</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.alias}
            </option>
          ))}
        </select>
        <input placeholder="네이버 Place ID" value={placeId} onChange={(e) => setPlaceId(e.target.value)} />
        <input placeholder="상호명" value={bizName} onChange={(e) => setBizName(e.target.value)} />
        <button className="btn btn--primary" onClick={addPlace} disabled={!accountId || !placeId || !bizName}>
          가맹점 추가
        </button>

        <h3>가맹점 목록</h3>
        <ul className="list">
          {places.map((p) => (
            <li key={p.id}>
              <b>{p.businessName}</b> <span className="muted">placeId {p.placeId} · #{p.id}</span>
            </li>
          ))}
          {!places.length && <li className="muted">아직 없음</li>}
        </ul>
      </section>
    </div>
  );
}
