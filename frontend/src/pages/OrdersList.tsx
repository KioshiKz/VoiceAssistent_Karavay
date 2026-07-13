import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { ordersApi } from "../api/endpoints";
import type { OrderSummaryOut } from "../api/types";
import { ConsoleShell } from "../components/ConsoleShell";

export function OrdersList() {
  const [orders, setOrders] = useState<OrderSummaryOut[]>([]);
  const [loading, setLoading] = useState(false);

  function reload() {
    setLoading(true);
    ordersApi
      .list()
      .then(setOrders)
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  return (
    <ConsoleShell
      title="Все заявки"
      subtitle="Архив загруженных заявок — откройте любую для просмотра и редактирования."
      actions={
        <button type="button" onClick={reload} disabled={loading}>
          <RefreshCw size={17} />
          Обновить
        </button>
      }
    >
      {orders.length === 0 ? (
        <div className="empty-state">Заявок пока нет.</div>
      ) : (
        <table className="order-table">
          <thead>
            <tr>
              <th>Дата исполнения</th>
              <th>Файл</th>
              <th>Цех</th>
              <th>Позиций</th>
              <th>Загрузил</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id}>
                <td>{order.execution_date}</td>
                <td>{order.source_filename}</td>
                <td>{order.workshop_folder_name ?? "Без цеха"}</td>
                <td>
                  {order.active_lines}/{order.total_lines}
                </td>
                <td>{order.uploaded_by_name ?? "—"}</td>
                <td>
                  <Link to={`/orders/${order.id}`}>Открыть</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </ConsoleShell>
  );
}
