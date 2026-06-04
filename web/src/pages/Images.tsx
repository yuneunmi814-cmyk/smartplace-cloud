import { useEffect, useRef, useState } from 'react';
import { api, type ImageRes } from '../lib/api';

export function Images() {
  const [images, setImages] = useState<ImageRes[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    setImages(await api.listImages());
  }
  useEffect(() => {
    refresh().catch((e) => setError(String(e.message ?? e)));
  }, []);

  async function upload(files: File[]) {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    try {
      await api.uploadImages(files);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  return (
    <section className="card">
      <h2>이미지 업로드</h2>
      <p className="muted">
        업로드된 이미지는 AWS S3에 저장됩니다 (jpg/png/webp). <b>여러 장 한 번에</b> 선택할 수 있어요.
      </p>
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        disabled={busy}
        onChange={(e) => e.target.files && upload(Array.from(e.target.files))}
      />
      {busy && <p className="muted">업로드 중…</p>}
      {error && <p className="error">{error}</p>}

      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>파일명</th>
            <th>유형</th>
            <th>크기</th>
          </tr>
        </thead>
        <tbody>
          {images.map((i) => (
            <tr key={i.id}>
              <td>{i.id}</td>
              <td>{i.originalFilename}</td>
              <td>{i.contentType}</td>
              <td>{(i.sizeBytes / 1024).toFixed(1)} KB</td>
            </tr>
          ))}
          {!images.length && (
            <tr>
              <td colSpan={4} className="muted">
                업로드된 이미지가 없습니다.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}
