import { useParams } from "react-router-dom";
import { ConsoleShell } from "../components/ConsoleShell";
import { ExecutionPanel } from "../components/ExecutionPanel";

export function ExecutionView() {
  const { orderLineId } = useParams();

  return (
    <ConsoleShell title="Выполнение заявки" subtitle="Пошаговое выполнение текущей строки заявки с голосовыми командами.">
      <ExecutionPanel orderLineId={orderLineId ?? null} />
    </ConsoleShell>
  );
}
