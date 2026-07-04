import type { MeasureType } from "../api/types";

export const DISPLAY_UNITS: Record<MeasureType, { unit: string; label: string; factor: number }[]> = {
  weight: [
    { unit: "g", label: "г", factor: 1 },
    { unit: "kg", label: "кг", factor: 1000 },
    { unit: "t", label: "т", factor: 1_000_000 },
  ],
  volume: [
    { unit: "ml", label: "мл", factor: 1 },
    { unit: "l", label: "л", factor: 1000 },
  ],
  time: [
    { unit: "sec", label: "сек", factor: 1 },
    { unit: "min", label: "мин", factor: 60 },
    { unit: "hour", label: "ч", factor: 3600 },
  ],
  temperature: [{ unit: "celsius", label: "°C", factor: 1 }],
  count: [{ unit: "pcs", label: "шт", factor: 1 }],
};

export function parseDecimalInput(value: string): number {
  const normalized = value.trim().replace(",", ".");
  if (!normalized) return 0;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function quantize(value: number): number {
  return Math.round((value + Number.EPSILON) * 1000) / 1000;
}

function trim(value: number): string {
  return quantize(value).toLocaleString("ru-RU", {
    maximumFractionDigits: 3,
    useGrouping: false,
  });
}

export function toCanonical(value: string, unit: string, measureType: MeasureType): number {
  const factor = DISPLAY_UNITS[measureType].find((item) => item.unit === unit)?.factor ?? 1;
  return quantize(parseDecimalInput(value) * factor);
}

export function formatCompound(valueCanonical: number, measureType: MeasureType): string {
  const value = quantize(valueCanonical);
  if (measureType === "weight") {
    const kg = Math.floor(value / 1000);
    const g = quantize(value - kg * 1000);
    if (kg && g) return `${kg} кг ${trim(g)} г`;
    if (kg) return `${kg} кг`;
    return `${trim(g)} г`;
  }
  if (measureType === "volume") {
    const l = Math.floor(value / 1000);
    const ml = quantize(value - l * 1000);
    if (l && ml) return `${l} л ${trim(ml)} мл`;
    if (l) return `${l} л`;
    return `${trim(ml)} мл`;
  }
  if (measureType === "time") {
    const h = Math.floor(value / 3600);
    const m = Math.floor((value % 3600) / 60);
    const s = quantize(value - h * 3600 - m * 60);
    const parts = [h && `${h} ч`, m && `${m} мин`, s && `${trim(s)} сек`].filter(Boolean);
    return parts.length ? parts.join(" ") : "0 сек";
  }
  if (measureType === "temperature") {
    return `${trim(value)} °C`;
  }
  return `${trim(value)} шт`;
}
