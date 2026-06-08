import { useEffect, useState } from 'react';
import { getRole, api, type LicenseAdmin, type LicenseDetail } from '../lib/api';

export function License() {
  const isAdmin = getRole() === 'admin';
  const [mine, setMine] = useState<LicenseDetail[]>([]);
  const [all, setAll] = useState<LicenseAdmin[]>([]);
  const [error, setError] = useState<string | null>(null);

  // issue form (admin)
  const [email, setEmail] = useState('');
  const [plan, setPlan] = useState('basic');
  const [seats, setSeats] = useState(1);
  const [days, setDays] = useState<number | ''>('');
  const [issued, setIssued] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      setMine(await api.myLicenses());
      if (isAdmin) setAll(await api.listLicenses());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  async function issue() {
    setError(null);
    setIssued(null);
    try {
      const r = await api.createLicense({ email, plan, seats, days: days === '' ? undefined : Number(days) });
      setIssued(r.licenseKey);
      setEmail('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function release(licenseId: number, deviceId: number) {
    if (!confirm('이 기기를 해제하면 좌석 1개가 반환됩니다. 계속할까요?')) return;
    try {
      await api.deactivateDevice(licenseId, deviceId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function revoke(id: number) {
    if (!confirm('이 라이선스를 취소하면 이후 활성화가 거부됩니다. 계속할까요?')) return;
    try {
      await api.revokeLicense(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="grid2">
      <section className="card">
        <h2>내 라이선스</h2>
        {error && <p className="error">{error}</p>}
        {!mine.length && <p className="muted">발급된 라이선스가 없습니다.</p>}
        {mine.map((lic) => (
          <div key={lic.id} className="lic">
            <div className="row-actions" style={{ justifyContent: 'space-between' }}>
              <code>{lic.licenseKey}</code>
              <span className="muted">
                {lic.plan} · 좌석 {lic.devices.length}/{lic.seats} ·{' '}
                {lic.status === 'active' ? `~${new Date(lic.expiresAt).toLocaleDateString()}` : lic.status}
              </span>
            </div>
            <ul className="list">
              {lic.devices.map((d) => (
                <li key={d.id} className="row-actions" style={{ justifyContent: 'space-between' }}>
                  <span>
                    {d.name || '이름 없는 기기'}{' '}
                    <span className="muted">
                      {d.lastSeenAt ? `· 최근 ${new Date(d.lastSeenAt).toLocaleDateString()}` : ''}
                    </span>
                  </span>
                  <button className="btn btn--ghost" onClick={() => release(lic.id, d.id)}>
                    해제
                  </button>
                </li>
              ))}
              {!lic.devices.length && <li className="muted">활성화된 기기 없음</li>}
            </ul>
          </div>
        ))}
      </section>

      {isAdmin && (
        <section className="card">
          <h2>라이선스 발급 (관리자)</h2>
          <input placeholder="대상 사용자 이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
          <div className="row-actions">
            <select value={plan} onChange={(e) => setPlan(e.target.value)}>
              <option value="basic">basic</option>
              <option value="pro">pro</option>
            </select>
            <input
              type="number"
              min={1}
              placeholder="좌석"
              value={seats}
              onChange={(e) => setSeats(Number(e.target.value))}
              style={{ width: 90 }}
            />
            <input
              type="number"
              min={1}
              placeholder="유효일(기본 365)"
              value={days}
              onChange={(e) => setDays(e.target.value === '' ? '' : Number(e.target.value))}
              style={{ width: 140 }}
            />
          </div>
          <button className="btn btn--primary" onClick={issue} disabled={!email}>
            발급
          </button>
          {issued && (
            <p className="muted">
              발급됨 — 키: <code>{issued}</code> (이 키를 사용자에게 전달)
            </p>
          )}

          <h3>전체 라이선스</h3>
          <table className="table">
            <thead>
              <tr>
                <th>키</th>
                <th>소유자</th>
                <th>좌석</th>
                <th>상태</th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              {all.map((l) => (
                <tr key={l.id}>
                  <td>
                    <code>{l.licenseKey}</code>
                  </td>
                  <td className="muted">{l.ownerEmail}</td>
                  <td>
                    {l.devicesUsed}/{l.seats}
                  </td>
                  <td>{l.status}</td>
                  <td className="row-actions">
                    {l.status === 'active' && (
                      <button className="btn btn--ghost" onClick={() => revoke(l.id)}>
                        취소
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!all.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    발급된 라이선스 없음
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
