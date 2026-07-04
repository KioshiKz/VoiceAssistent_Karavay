import { ArrowDown, ArrowUp, BellRing, Trash2, Wheat, Workflow } from "lucide-react";
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
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    const phrase = String(params.start_phrase ?? "старт");
    return `таймер ${minutes ? `${minutes} мин ` : ""}${rest} сек, фраза: ${phrase}`;
  }
  if (step.event_template?.event_type === "weight_check") {
    return `проверка веса: ${params.target_weight_g ?? "?"} г ± ${params.tolerance_g ?? 0} г`;
  }
  if (step.event_template?.event_type === "phrase_confirmation") {
    return `подтвердить фразой: «${params.phrase ?? ""}»`;
  }
  return "";
}

function stepTitle(step: RecipeStepOut) {
  if (step.step_type === "ingredient") return step.ingredient?.name;
  if (step.step_type === "ingredient_event") return `${step.event_template?.name ?? "Событие"} + ${step.ingredient?.name ?? "ингредиент"}`;
  return step.event_template?.name;
}

function stepSummary(step: RecipeStepOut) {
  if (step.step_type === "ingredient") return step.quantity_display;
  if (step.step_type === "ingredient_event") return `${step.quantity_display ?? ""} · ${eventSummary(step)}`;
  return eventSummary(step);
}

export function RecipeStepList({ steps, onMoveUp, onMoveDown, onDelete }: RecipeStepListProps) {
  if (steps.length === 0) {
    return <div className="empty-folder">В рецептуре пока нет шагов.</div>;
  }

  return (
    <div className="recipe-steps">
      {steps.map((step, index) => {
        const Icon = step.step_type === "ingredient" ? Wheat : step.step_type === "ingredient_event" ? Workflow : BellRing;
        return (
          <div className="recipe-step-row" key={step.id}>
            <span className="index">{index + 1}.</span>
            <Icon size={18} />
            <span className="title">{stepTitle(step)}</span>
            <span className="muted">{stepSummary(step)}</span>
            <button type="button" onClick={() => onMoveUp(step.id)} disabled={index === 0} title="Выше">
              <ArrowUp size={16} />
            </button>
            <button type="button" onClick={() => onMoveDown(step.id)} disabled={index === steps.length - 1} title="Ниже">
              <ArrowDown size={16} />
            </button>
            <button type="button" className="danger" onClick={() => onDelete(step.id)} title="Удалить">
              <Trash2 size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
