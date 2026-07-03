import type { RecipeStepOut } from "../api/types";

interface RecipeStepListProps {
  steps: RecipeStepOut[];
  onMoveUp: (stepId: string) => void;
  onMoveDown: (stepId: string) => void;
  onDelete: (stepId: string) => void;
}

function eventSummary(step: RecipeStepOut): string {
  const params = step.event_params ?? {};
  if (step.event_template?.event_type === "timer") {
    const seconds = Number(params.duration_seconds ?? 0);
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `таймер ${m ? `${m} мин ` : ""}${s} сек`;
  }
  if (step.event_template?.event_type === "weight_check") {
    return `проверка веса: ${params.target_weight_g ?? "?"} г ± ${params.tolerance_g ?? 0} г`;
  }
  if (step.event_template?.event_type === "phrase_confirmation") {
    return `подтвердить фразой: «${params.phrase ?? ""}»`;
  }
  return "";
}

export function RecipeStepList({ steps, onMoveUp, onMoveDown, onDelete }: RecipeStepListProps) {
  return (
    <div className="recipe-steps">
      {steps.map((step, idx) => (
        <div className="recipe-step-row" key={step.id}>
          <span className="index">{idx + 1}.</span>
          <span>{step.step_type === "ingredient" ? "🧂" : "⏱"}</span>
          <span className="title">
            {step.step_type === "ingredient" ? step.ingredient?.name : step.event_template?.name}
          </span>
          <span style={{ color: "#555" }}>
            {step.step_type === "ingredient" ? step.quantity_display : eventSummary(step)}
          </span>
          <button onClick={() => onMoveUp(step.id)} disabled={idx === 0}>
            ↑
          </button>
          <button onClick={() => onMoveDown(step.id)} disabled={idx === steps.length - 1}>
            ↓
          </button>
          <button onClick={() => onDelete(step.id)}>✕</button>
        </div>
      ))}
    </div>
  );
}
