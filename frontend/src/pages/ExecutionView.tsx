import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { executionApi } from "../api/endpoints";
import type { ExecutionPlanOut } from "../api/types";

export function ExecutionView() {
  const { orderLineId } = useParams();
  const [plan, setPlan] = useState<ExecutionPlanOut | null>(null);
  const [advancing, setAdvancing] = useState(false);

  useEffect(() => {
    if (!orderLineId) return;
    executionApi.getOrCreate(orderLineId).then(setPlan);
  }, [orderLineId]);

  if (!plan) return <div className="execution-page">Загрузка...</div>;

  const currentStep = plan.steps[plan.current_step_index];

  async function advance() {
    if (!plan) return;
    setAdvancing(true);
    try {
      const updated = await executionApi.advance(plan.id);
      setPlan(updated);
    } finally {
      setAdvancing(false);
    }
  }

  return (
    <div className="execution-page">
      <div style={{ textAlign: "left", marginBottom: 16 }}>
        <Link to="/orders/current">← К заявке</Link>
      </div>

      <div className="execution-progress">
        {plan.steps.map((s, idx) => (
          <span
            key={idx}
            className={`dot${s.status === "done" ? " done" : ""}${idx === plan.current_step_index ? " current" : ""}`}
          />
        ))}
      </div>

      {plan.status === "completed" ? (
        <div className="execution-step-card">
          <div className="step-kind">Готово</div>
          <div className="step-name">Все шаги выполнены ✅</div>
        </div>
      ) : (
        <div className="execution-step-card">
          <div className="step-kind">{currentStep.step_type === "ingredient" ? "Ингредиент" : "Событие"}</div>
          <div className="step-name">
            {currentStep.step_type === "ingredient" ? currentStep.ingredient_name_snapshot : currentStep.event_name_snapshot}
          </div>
          {currentStep.step_type === "ingredient" ? (
            <div className="step-quantity">{currentStep.quantity_display}</div>
          ) : (
            <div className="step-quantity">
              {currentStep.event_type_snapshot === "timer" &&
                `Таймер: ${Math.floor(Number(currentStep.event_params_snapshot?.duration_seconds ?? 0) / 60)} мин ${
                  Number(currentStep.event_params_snapshot?.duration_seconds ?? 0) % 60
                } сек`}
              {currentStep.event_type_snapshot === "weight_check" &&
                `Целевой вес: ${currentStep.event_params_snapshot?.target_weight_g} г ± ${currentStep.event_params_snapshot?.tolerance_g} г`}
              {currentStep.event_type_snapshot === "phrase_confirmation" &&
                `Подтвердить фразой: «${currentStep.event_params_snapshot?.phrase}»`}
            </div>
          )}
        </div>
      )}

      {plan.status !== "completed" && (
        <button className="primary" style={{ width: "100%", padding: 14, fontSize: 16 }} onClick={advance} disabled={advancing}>
          Дальше
        </button>
      )}
    </div>
  );
}
