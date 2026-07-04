import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import type { MeasureType } from "../api/types";
import { DISPLAY_UNITS, formatCompound, toCanonical } from "../utils/units";

interface UnitQuantityInputProps {
  measureType: MeasureType;
  valueCanonical: number;
  onChange: (canonical: number) => void;
}

/** Compound entry combines one or two display units into the canonical Decimal-like number stored by the backend. */
export function UnitQuantityInput({ measureType, valueCanonical, onChange }: UnitQuantityInputProps) {
  const units = DISPLAY_UNITS[measureType];
  const defaultUnit = units[units.length > 1 ? 1 : 0].unit;
  const baseUnit = units[0].unit;
  const [showCompound, setShowCompound] = useState(false);

  const [unit1, setUnit1] = useState(defaultUnit);
  const [value1, setValue1] = useState("");
  const [unit2, setUnit2] = useState(baseUnit);
  const [value2, setValue2] = useState("");

  useEffect(() => {
    setShowCompound(false);
    setUnit1(defaultUnit);
    setValue1("");
    setUnit2(baseUnit);
    setValue2("");
    onChange(0);
  }, [baseUnit, defaultUnit, onChange]);

  function recompute(v1: string, u1: string, compound: boolean, v2: string, u2: string) {
    const first = toCanonical(v1, u1, measureType);
    const second = compound ? toCanonical(v2, u2, measureType) : 0;
    onChange(Math.round((first + second + Number.EPSILON) * 1000) / 1000);
  }

  return (
    <div className="quantity-input">
      <div className="pair">
        <input
          type="text"
          inputMode="decimal"
          value={value1}
          placeholder="0"
          onChange={(event) => {
            const value = event.target.value;
            setValue1(value);
            recompute(value, unit1, showCompound, value2, unit2);
          }}
        />
        <select
          value={unit1}
          onChange={(event) => {
            setUnit1(event.target.value);
            recompute(value1, event.target.value, showCompound, value2, unit2);
          }}
        >
          {units.map((unit) => (
            <option key={unit.unit} value={unit.unit}>
              {unit.label}
            </option>
          ))}
        </select>
      </div>

      {units.length > 1 && !showCompound && (
        <button type="button" onClick={() => setShowCompound(true)}>
          <Plus size={16} />
          Единица
        </button>
      )}

      {showCompound && (
        <div className="pair">
          <input
            type="text"
            inputMode="decimal"
            value={value2}
            placeholder="0"
            onChange={(event) => {
              const value = event.target.value;
              setValue2(value);
              recompute(value1, unit1, true, value, unit2);
            }}
          />
          <select
            value={unit2}
            onChange={(event) => {
              setUnit2(event.target.value);
              recompute(value1, unit1, true, value2, event.target.value);
            }}
          >
            {units.map((unit) => (
              <option key={unit.unit} value={unit.unit}>
                {unit.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              setShowCompound(false);
              setValue2("");
              recompute(value1, unit1, false, "", unit2);
            }}
            title="Убрать вторую единицу"
          >
            <X size={16} />
          </button>
        </div>
      )}

      <span className="muted">= {formatCompound(valueCanonical, measureType)}</span>
    </div>
  );
}
