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
};

export function formatCompound(valueCanonical: number, measureType: MeasureType): string {
  if (measureType === "weight") {
    const kg = Math.floor(valueCanonical / 1000);
    const g = valueCanonical % 1000;
    return kg ? `${kg} кг ${g} г` : `${g} г`;
  }
  if (measureType === "volume") {
    const l = Math.floor(valueCanonical / 1000);
    const ml = valueCanonical % 1000;
    return l ? `${l} л ${ml} мл` : `${ml} мл`;
  }
  if (measureType === "time") {
    const h = Math.floor(valueCanonical / 3600);
    const m = Math.floor((valueCanonical % 3600) / 60);
    const s = valueCanonical % 60;
    const parts = [h && `${h} ч`, m && `${m} мин`, s && `${s} сек`].filter(Boolean);
    return parts.length ? parts.join(" ") : "0 сек";
  }
  return `${(valueCanonical / 10).toFixed(1)} °C`;
}
