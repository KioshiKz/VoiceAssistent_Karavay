import { useState } from "react";
import type { MeasureType } from "../api/types";
import { DISPLAY_UNITS, formatCompound } from "../utils/units";

interface UnitQuantityInputProps {
  measureType: MeasureType;
  valueCanonical: number;
  onChange: (canonical: number) => void;
}

/** Compound entry (e.g. "3 л 200 мл"): value1/unit1 + optional value2/unit2,
 * combined into the single canonical integer the backend stores. */
export function UnitQuantityInput({ measureType, valueCanonical, onChange }: UnitQuantityInputProps) {
  const units = DISPLAY_UNITS[measureType];
  const [showCompound, setShowCompound] = useState(false);

  const [unit1, setUnit1] = useState(units[units.length > 1 ? 1 : 0].unit);
  const [value1, setValue1] = useState(0);
  const [unit2, setUnit2] = useState(units[0].unit);
  const [value2, setValue2] = useState(0);

  function recompute(v1: number, u1: string, compound: boolean, v2: number, u2: string) {
    const f1 = units.find((u) => u.unit === u1)!.factor;
    let canonical = Math.round(v1 * f1);
    if (compound) {
      const f2 = units.find((u) => u.unit === u2)!.factor;
      canonical += Math.round(v2 * f2);
    }
    onChange(canonical);
  }

  return (
    <div className="quantity-input">
      <div className="pair">
        <input
          type="number"
          value={value1}
          onChange={(e) => {
            const v = Number(e.target.value);
            setValue1(v);
            recompute(v, unit1, showCompound, value2, unit2);
          }}
        />
        <select
          value={unit1}
          onChange={(e) => {
            setUnit1(e.target.value);
            recompute(value1, e.target.value, showCompound, value2, unit2);
          }}
        >
          {units.map((u) => (
            <option key={u.unit} value={u.unit}>
              {u.label}
            </option>
          ))}
        </select>
      </div>

      {units.length > 1 && !showCompound && (
        <button type="button" onClick={() => setShowCompound(true)}>
          + добавить единицу
        </button>
      )}

      {showCompound && (
        <div className="pair">
          <input
            type="number"
            value={value2}
            onChange={(e) => {
              const v = Number(e.target.value);
              setValue2(v);
              recompute(value1, unit1, true, v, unit2);
            }}
          />
          <select
            value={unit2}
            onChange={(e) => {
              setUnit2(e.target.value);
              recompute(value1, unit1, true, value2, e.target.value);
            }}
          >
            {units.map((u) => (
              <option key={u.unit} value={u.unit}>
                {u.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              setShowCompound(false);
              setValue2(0);
              recompute(value1, unit1, false, 0, unit2);
            }}
          >
            ✕
          </button>
        </div>
      )}

      <span style={{ color: "#888", fontSize: 13 }}>= {formatCompound(valueCanonical, measureType)}</span>
    </div>
  );
}
