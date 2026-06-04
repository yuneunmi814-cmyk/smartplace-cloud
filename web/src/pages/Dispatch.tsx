import { useEffect, useState } from 'react';
import { api, type ImageRes, type Place } from '../lib/api';

export function Dispatch() {
  const [images, setImages] = useState<ImageRes[]>([]);
  const [places, setPlaces] = useState<Place[]>([]);
  const [imageId, setImageId] = useState<number | ''>('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [scheduledAt, setScheduledAt] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listImages(), api.listPlaces()])
      .then(([imgs, pls]) => {
        setImages(imgs);
        setPlaces(pls);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(places.map((p) => p.id)));
  }
  function clearAll() {
    setSelected(new Set());
  }

  async function dispatch() {
    setError(null);
    setResult(null);
    try {
      const task = await api.dispatch(
        Number(imageId),
        [...selected],
        scheduledAt ? new Date(scheduledAt).toISOString() : null,
      );
      setResult(`작업 #${task.id} 생성됨 (${task.status}) · 대상 ${task.items.length}곳`);
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <section className="card">
      <h2>이미지 일괄 배포</h2>
      <label className="field">
        <span>이미지 선택</span>
        <select value={imageId} onChange={(e) => setImageId(Number(e.target.value))}>
          <option value="">이미지 선택</option>
          {images.map((i) => (
            <option key={i.id} value={i.id}>
              #{i.id} {i.originalFilename}
            </option>
          ))}
        </select>
      </label>

      <div className="field">
        <span>
          적용할 가맹점 ({selected.size}/{places.length}곳 선택)
          <button className="btn btn--ghost mini" type="button" onClick={selectAll}>
            전체 선택
          </button>
          <button className="btn btn--ghost mini" type="button" onClick={clearAll}>
            전체 해제
          </button>
        </span>
        <div className="checklist">
          {places.map((p) => (
            <label key={p.id} className="check">
              <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
              {p.businessName} <span className="muted">({p.placeId})</span>
            </label>
          ))}
          {!places.length && <span className="muted">먼저 가맹점을 등록하세요.</span>}
        </div>
      </div>

      <label className="field">
        <span>예약 시간 (선택 — 비우면 즉시 실행)</span>
        <input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
      </label>

      {error && <p className="error">{error}</p>}
      {result && <p className="success">{result}</p>}
      <button className="btn btn--primary" onClick={dispatch} disabled={!imageId || selected.size === 0}>
        배포 실행
      </button>
    </section>
  );
}
