export function weightCheckDefaults(params: Record<string, unknown> | null = null): Record<string, unknown> {
  return {
    tolerance_unit: params?.tolerance_unit ?? "g",
    tolerance_below: params?.tolerance_below ?? params?.tolerance_g ?? 0,
    tolerance_above: params?.tolerance_above ?? params?.tolerance_g ?? 0,
    duration_seconds: params?.duration_seconds ?? 5,
    enforce_minimum_weight: params?.enforce_minimum_weight ?? true,
  };
}

export function weightCheckError(params: Record<string, unknown>, requireTarget = false): string | null {
  const values = weightCheckDefaults(params);
  if (values.tolerance_unit !== "g" && values.tolerance_unit !== "percent") return "Выберите проценты или граммы.";
  for (const key of ["tolerance_below", "tolerance_above"]) {
    if (values[key] === "" || !Number.isFinite(Number(values[key])) || Number(values[key]) < 0) {
      return "Допустимые отклонения должны быть неотрицательными числами.";
    }
  }
  const duration = Number(values.duration_seconds);
  if (!Number.isInteger(duration) || duration < 1 || duration > 86400) return "Длительность проверки: от 1 до 86400 целых секунд.";
  if (requireTarget && (!Number.isFinite(Number(params.target_weight_g)) || Number(params.target_weight_g) <= 0)) {
    return "Укажите положительный целевой вес в граммах.";
  }
  return null;
}

export function serializeWeightSettings(params: Record<string, unknown>): Record<string, unknown> {
  const values = weightCheckDefaults(params);
  return {
    tolerance_unit: values.tolerance_unit,
    tolerance_below: Number(values.tolerance_below),
    tolerance_above: Number(values.tolerance_above),
    duration_seconds: Number(values.duration_seconds),
    enforce_minimum_weight: values.enforce_minimum_weight,
  };
}

export function weightCheckSummary(params: Record<string, unknown>): string {
  const values = weightCheckDefaults(params);
  const unit = values.tolerance_unit === "percent" ? "%" : " г";
  return `${params.target_weight_g ?? "?"} г, −${values.tolerance_below}${unit} / +${values.tolerance_above}${unit}, без колебаний ${values.duration_seconds} сек`;
}
