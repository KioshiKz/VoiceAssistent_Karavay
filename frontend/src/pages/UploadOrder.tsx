import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ordersApi } from "../api/endpoints";
import type { OrderUploadOut } from "../api/types";

export function UploadOrder() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [executionDate, setExecutionDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [result, setResult] = useState<OrderUploadOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    try {
      const res = await ordersApi.upload(file, executionDate);
      setResult(res);
    } catch {
      setError("Не удалось загрузить файл. Проверьте формат (3 строки на позицию: название/количество/время).");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="editor-page">
      <Link to="/">← Главная</Link>
      <h2>Загрузить заявку</h2>

      <div className="editor-field">
        <label>Дата исполнения</label>
        <input type="date" value={executionDate} onChange={(e) => setExecutionDate(e.target.value)} />
      </div>

      <div
        className="upload-dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        onClick={() => fileInputRef.current?.click()}
      >
        {uploading ? "Загрузка..." : "Перетащите .xlsx сюда или нажмите, чтобы выбрать файл"}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </div>

      {error && <p className="error-text">{error}</p>}

      {result && (
        <div style={{ marginTop: 20 }}>
          <p>
            Всего строк: {result.total_lines}, найдено: {result.matched}, не найдено: {result.unmatched}
          </p>
          <table className="order-table">
            <thead>
              <tr>
                <th>Продукция</th>
                <th>Количество</th>
                <th>Время</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {result.lines.map((l) => (
                <tr key={l.id}>
                  <td>{l.product_name_raw}</td>
                  <td>{l.quantity}</td>
                  <td>{l.due_time.slice(0, 5)}</td>
                  <td>
                    <span className={`badge ${l.match_status}`}>
                      {l.match_status === "matched" ? "найдено" : "не найдено"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button className="primary" style={{ marginTop: 16 }} onClick={() => navigate("/orders/current")}>
            Перейти к текущей заявке
          </button>
        </div>
      )}
    </div>
  );
}
