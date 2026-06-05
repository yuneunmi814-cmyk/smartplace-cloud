import { useEffect, useState } from 'react';
import { api, type ImageRes, type Place } from '../lib/api';

export function Dispatch() {
  const [images, setImages] = useState<ImageRes[]>([]);
  const [places, setPlaces] = useState<Place[]>([]);
  const [selectedImages, setSelectedImages] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [scheduledAt, setScheduledAt] = useState('');
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.listImages(), api.listPlaces()])
      .then(([imgs, pls]) => {
        setImages(imgs);
        setPlaces(pls);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  function toggleImage(id: number) {
    setSelectedImages((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function dispatch() {
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const imageIds = [...selectedImages];
      const placeIds = [...selected];
      const iso = scheduledAt ? new Date(scheduledAt).toISOString() : null;
      // One task per image (each image → all selected places).
      for (const imageId of imageIds) {
        await api.dispatch(imageId, placeIds, iso);
      }
      setResult(
        `작업 ${imageIds.length}개 생성됨 (이미지 ${imageIds.length}장 × 가맹점 ${placeIds.length}곳). 작업 현황에서 진행을 확인하세요.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>이미지 일괄 배포</h2>

      <div className="field">
        <span>
          적용할 이미지 ({selectedImages.size}/{images.length}장 선택)
          <button className="btn btn--ghost mini" type="button" onClick={() => setSelectedImages(new Set(images.map((i) => i.id)))}>
            전체 선택
          </button>
          <button className="btn btn--ghost mini" type="button" onClick={() => setSelectedImages(new Set())}>
            전체 해제
          </button>
        </span>
        <div className="checklist">
          {images.map((i) => (
            <label key={i.id} className="check">
              <input type="checkbox" checked={selectedImages.has(i.id)} onChange={() => toggleImage(i.id)} />
              #{i.id} {i.originalFilename}{' '}
              <span className="muted">({(i.sizeBytes / 1024).toFixed(0)}KB)</span>
            </label>
          ))}
          {!images.length && <span className="muted">먼저 이미지를 업로드하세요.</span>}
        </div>
      </div>

      <div className="field">
        <span>
          적용할 가맹점 ({selected.size}/{places.length}곳 선택)
          <button className="btn btn--ghost mini" type="button" onClick={() => setSelected(new Set(places.map((p) => p.id)))}>
            전체 선택
          </button>
          <button className="btn btn--ghost mini" type="button" onClick={() => setSelected(new Set())}>
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
      <button
        className="btn btn--primary"
        onClick={dispatch}
        disabled={busy || selectedImages.size === 0 || selected.size === 0}
      >
        {busy ? '생성 중…' : '배포 실행'}
      </button>
    </section>
  );
}
