import { useEffect, useMemo, useRef, useState } from "react";
import { FileUp } from "lucide-react";
import { foldersApi, ordersApi } from "../api/endpoints";
import type { FolderOut, OrderUploadOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";

function folderLabel(folder: FolderOut, folders: FolderOut[]) {
  const byId = new Map(folders.map((item) => [item.id, item]));
  const parts = [folder.name];
  let parent = folder.parent_id ? byId.get(folder.parent_id) : null;
  while (parent) {
    parts.unshift(parent.name);
    parent = parent.parent_id ? byId.get(parent.parent_id) : null;
  }
  return parts.join(" / ");
}

export function UploadOrder() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [executionDate, setExecutionDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [folders, setFolders] = useState<FolderOut[]>([]);
  const [workshopFolderId, setWorkshopFolderId] = useState<string>("");
  const [result, setResult] = useState<OrderUploadOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    foldersApi.tree().then(setFolders);
  }, []);

  const folderOptions = useMemo(
    () => [...folders].sort((a, b) => folderLabel(a, folders).localeCompare(folderLabel(b, folders), "ru")),
    [folders],
  );

  async function handleFile(file: File) {
    setError(null);
    setUploading(true);
    try {
      const res = await ordersApi.upload(file, executionDate, workshopFolderId || null);
      setResult(res);
    } catch {
      setError("Не удалось загрузить файл. Проверьте формат: название, количество и время для каждой позиции.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <ConsoleShell title="Загрузка заявки" subtitle="Загрузите Excel-заявку и привяжите её к нужному цеху.">
      <div className="order-upload-layout">
        <section className="editor-card">
          <div className="pane-heading">
            <div>
              <p className="eyebrow">Параметры</p>
              <h2>Новая заявка</h2>
            </div>
          </div>

          <label className="editor-field">
            Дата исполнения
            <input type="date" value={executionDate} onChange={(event) => setExecutionDate(event.target.value)} />
          </label>

          <label className="editor-field">
            Цех / папка
            <select value={workshopFolderId} onChange={(event) => setWorkshopFolderId(event.target.value)}>
              <option value="">Общая заявка без цеха</option>
              {folderOptions.map((folder) => (
                <option key={folder.id} value={folder.id}>
                  {folderLabel(folder, folders)}
                </option>
              ))}
            </select>
          </label>

          <div
            className="upload-dropzone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const file = event.dataTransfer.files[0];
              if (file) void handleFile(file);
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <FileUp size={28} />
            <strong>{uploading ? "Загрузка..." : "Перетащите .xlsx сюда или нажмите, чтобы выбрать файл"}</strong>
            <span>Продукция и ингредиенты остаются общей базой, цех ограничивает видимость заявки.</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleFile(file);
              }}
            />
          </div>

          {error && <p className="error-text">{error}</p>}
        </section>

        {result && (
          <section className="editor-card">
            <div className="pane-heading">
              <div>
                <p className="eyebrow">Результат</p>
                <h2>
                  {result.total_lines} строк, найдено {result.matched}
                </h2>
              </div>
            </div>
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
                {result.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.product_name_raw}</td>
                    <td>{line.quantity}</td>
                    <td>{line.due_time.slice(0, 5)}</td>
                    <td>
                      <span className={`badge ${line.match_status}`}>
                        {line.match_status === "matched" ? "найдено" : "не найдено"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>
    </ConsoleShell>
  );
}
