import type { ExecutionPlanStepOut } from "../api/types";

export function stepSpeech(step: ExecutionPlanStepOut): string {
  const ingredient = [step.ingredient_name_snapshot ?? "ингредиент", step.quantity_display].filter(Boolean).join(", ");
  if (step.step_type === "ingredient") return `${ingredient}.`;
  const action = step.event_type_snapshot === "weight_check"
    ? "Взвешивание"
    : step.event_name_snapshot?.trim() || "Событие";
  if (step.step_type === "ingredient_event") return `Постепенно добавить ${ingredient}. ${action}.`;
  return `${action}.`;
}
