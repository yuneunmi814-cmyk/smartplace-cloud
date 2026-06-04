import { useEffect, useState } from 'react';
import { api, type Task } from '../lib/api';

const STATUS_LABEL: Record<string, string> = {
  pending: '대기(예약)',
  queued: '큐 대기',
  running: '실행 중',
  success: '성공',
  partial: '부분 성공',
  failed: '실패',
  canceled: '취소됨',
};

export function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setTasks(await api.listTasks());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2500); // poll for worker progress
    return () => clearInterval(id);
  }, []);

  async function cancel(id: number) {
    await api.cancelTask(id).catch((e) => setError(String(e.message ?? e)));
    refresh();
  }

  return (
    <section className="card">
      <h2>작업 현황</h2>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>작업</th>
            <th>이미지</th>
            <th>상태</th>
            <th>대상 / 성공 / 실패</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => {
            const ok = t.items.filter((i) => i.status === 'ok').length;
            const fail = t.items.filter((i) => i.status === 'fail').length;
            return (
              <tr key={t.id}>
                <td>#{t.id}</td>
                <td>#{t.imageId}</td>
                <td>
                  <span className={`status status--${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
                </td>
                <td>
                  {t.items.length} / <span className="ok">{ok}</span> / <span className="fail">{fail}</span>
                </td>
                <td>
                  {(t.status === 'pending' || t.status === 'queued') && (
                    <button className="btn btn--ghost" onClick={() => cancel(t.id)}>
                      취소
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
          {!tasks.length && (
            <tr>
              <td colSpan={5} className="muted">
                아직 작업이 없습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
