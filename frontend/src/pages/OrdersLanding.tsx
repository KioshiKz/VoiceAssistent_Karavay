import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { foldersApi } from "../api/endpoints";
import type { FolderOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";

export function OrdersLanding() {
  const [workshops, setWorkshops] = useState<FolderOut[] | null>(null);

  useEffect(() => {
    foldersApi
      .tree()
      .then((folders) => setWorkshops(folders.filter((folder) => folder.parent_id === null)))
      .catch(() => setWorkshops([]));
  }, []);

  if (workshops?.[0]) {
    return <Navigate to={`/workshops/${workshops[0].id}/orders`} replace />;
  }

  return (
    <ConsoleShell title="Заявки" subtitle="Заявки разделены по доступным производственным цехам.">
      <div className="empty-state">
        {workshops === null ? "Загрузка списка цехов..." : "Нет доступных цехов. Обратитесь к администратору."}
      </div>
    </ConsoleShell>
  );
}
