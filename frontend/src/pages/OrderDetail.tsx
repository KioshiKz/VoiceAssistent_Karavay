import { useCallback } from "react";
import { useParams } from "react-router-dom";
import { ordersApi } from "../api/endpoints";
import { OrderEditor } from "../components/OrderEditor";

export function OrderDetail() {
  const { orderId } = useParams<{ orderId: string }>();
  const fetchOrder = useCallback(() => ordersApi.getOrder(orderId as string), [orderId]);

  return (
    <OrderEditor
      fetchOrder={fetchOrder}
      editTabKey="orders_list"
      title="Заявка"
      subtitle="Состав, ход выполнения и история действий по заявке."
    />
  );
}
