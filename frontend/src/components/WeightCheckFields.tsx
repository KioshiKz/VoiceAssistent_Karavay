import { weightCheckDefaults } from "../utils/weightCheck";

interface WeightCheckFieldsProps {
  params: Record<string, unknown>;
  onChange: (params: Record<string, unknown>) => void;
  fieldClassName?: string;
}

export function WeightCheckFields({ params, onChange, fieldClassName = "modal-field" }: WeightCheckFieldsProps) {
  const values = weightCheckDefaults(params);
  const unit = values.tolerance_unit === "percent" ? "%" : "г";
  return (
    <>
      <label className={fieldClassName}>
        Единица погрешности
        <select value={String(values.tolerance_unit)} onChange={(event) => onChange({ ...params, tolerance_unit: event.target.value })}>
          <option value="g">Граммы</option>
          <option value="percent">Проценты от целевого веса</option>
        </select>
      </label>
      <label className={fieldClassName}>
        Допустимое отклонение вниз (−), {unit}
        <input type="number" min="0" step="any" required value={String(values.tolerance_below)}
          onChange={(event) => onChange({ ...params, tolerance_below: event.target.value })} />
      </label>
      <label className={fieldClassName}>
        Допустимое отклонение вверх (+), {unit}
        <input type="number" min="0" step="any" required value={String(values.tolerance_above)}
          onChange={(event) => onChange({ ...params, tolerance_above: event.target.value })} />
      </label>
      <label className={fieldClassName}>
        Длительность проверки веса, секунд
        <input type="number" min="1" max="86400" step="1" required value={String(values.duration_seconds)}
          onChange={(event) => onChange({ ...params, duration_seconds: event.target.value })} />
      </label>
      <label className="checkbox-line span-2">
        <input type="checkbox" checked={values.enforce_minimum_weight !== false}
          onChange={(event) => onChange({ ...params, enforce_minimum_weight: event.target.checked })} />
        Защита: минимальный целевой вес 10 г
      </label>
    </>
  );
}
