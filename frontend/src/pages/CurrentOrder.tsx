import { ordersApi } from "../api/endpoints";
import { OrderEditor } from "../components/OrderEditor";

export function CurrentOrder() {
  return (
    <OrderEditor
      fetchOrder={ordersApi.current}
      editTabKey="current_order"
      title="Текущая заявка"
      subtitle="Просмотр очереди, сопоставление продукции, правки администратора и история изменений."
      allowCurrentSelection
    />
  );
}
