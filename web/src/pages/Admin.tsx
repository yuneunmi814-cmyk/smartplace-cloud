import { useEffect, useState } from 'react';
import { api, type AuditRow, type Stats, type UserRes } from '../lib/api';

export function Admin() {
  const [users, setUsers] = useState<UserRes[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const [u, a, s] = await Promise.all([api.listUsers(), api.audit(), api.stats()]);
      setUsers(u);
      setAudit(a);
      setStats(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="grid2">
      <section className="card">
        <h2>시스템 통계</h2>
        {error && <p className="error">{error}</p>}
        {stats && (
          <div className="stat-row">
            <Stat label="총 작업" value={String(stats.totalTasks)} />
            <Stat label="성공률" value={`${Math.round(stats.successRate * 100)}%`} />
            <Stat label="대기 작업" value={String(stats.pendingTasks)} />
            <Stat label="사용자" value={String(stats.users)} />
          </div>
        )}

        <h3>사용자 관리 (RBAC)</h3>
        <table className="table">
          <thead>
            <tr>
              <th>이메일</th>
              <th>역할</th>
              <th>상태</th>
              <th>액션</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.role}</td>
                <td>{u.status}</td>
                <td className="row-actions">
                  {u.status !== 'approved' && (
                    <button className="btn btn--ghost" onClick={() => api.approveUser(u.id).then(refresh)}>
                      승인
                    </button>
                  )}
                  <button
                    className="btn btn--ghost"
                    onClick={() => api.setRole(u.id, u.role === 'admin' ? 'user' : 'admin').then(refresh)}
                  >
                    {u.role === 'admin' ? '→user' : '→admin'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>감사 로그 (Audit Trail)</h2>
        <table className="table">
          <thead>
            <tr>
              <th>시각</th>
              <th>액터</th>
              <th>액션</th>
              <th>대상</th>
            </tr>
          </thead>
          <tbody>
            {audit.map((r) => (
              <tr key={r.id}>
                <td className="muted">{new Date(r.createdAt).toLocaleString()}</td>
                <td>{r.actorUserId ?? '-'}</td>
                <td>{r.action}</td>
                <td className="muted">
                  {r.targetType}#{r.targetId}
                </td>
              </tr>
            ))}
            {!audit.length && (
              <tr>
                <td colSpan={4} className="muted">
                  로그 없음
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat__value">{value}</div>
      <div className="stat__label">{label}</div>
    </div>
  );
}
