import { useRef, useState } from "react";
import { FileUp, X } from "lucide-react";
import { ordersApi } from "../api/endpoints";

interface OrderUploadDialogProps {
  workshopId: string;
  workshopName: string;
  onClose: () => void;
  onUploaded: (orderId: string) => void;
}

function localDateValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function OrderUploadDialog({ workshopId, workshopName, onClose, onUploaded }: OrderUploadDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [executionDate, setExecutionDate] = useState(localDateValue);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File) {
    if (uploading) return;
    setUploading(true);
    setError(null);
    try {
      const result = await ordersApi.upload(file, executionDate, workshopId);
      onUploaded(result.order_id);
    } catch {
      setError("Не удалось загрузить файл. Проверьте формат Excel и данные заявки.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={() => !uploading && onClose()}>
      <div className="modal-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Загрузить заявку</h2>
            <p>Цех: {workshopName}</p>
          </div>
          <button type="button" className="icon-button" onClick={onClose} disabled={uploading} title="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <label className="modal-field">
            Дата исполнения
            <input
              type="date"
              value={executionDate}
              onChange={(event) => setExecutionDate(event.target.value)}
              disabled={uploading}
            />
          </label>

          <div
            className={`upload-dropzone${uploading ? " disabled" : ""}`}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const file = event.dataTransfer.files[0];
              if (file) void upload(file);
            }}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            <FileUp size={30} />
            <strong>{uploading ? "Загрузка..." : "Выберите или перетащите .xlsx"}</strong>
            <span>Заявка будет создана в цехе «{workshopName}».</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
              }}
            />
          </div>

          {error && <p className="error-text">{error}</p>}
        </div>
      </div>
    </div>
  );
}
