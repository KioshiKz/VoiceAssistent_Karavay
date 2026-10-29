import { useMemo, useState } from "react";
import { apiClient } from "../api/client";
import { ConsoleShell } from "../components/ConsoleShell";
import { apiErrorMessage } from "../utils/apiError";

type Row = {
  warehouse: string;
  material: string;
  code: string;
  unit: string;
  norm: number;
  fact: number;
  fact_by_report: number;
  fact_by_act: number;
  fact_other: number;
  diff: number;
  diff_pct: number | null;
  // Present when costs were read from accounting postings.
  price?: number | null;
  fact_cost?: number;
  norm_cost?: number | null;
  diff_cost?: number | null;
  zero_cost_qty?: number;
};
type Costs = { fact: number; norm: number; diff: number; zero_cost_rows: number; incomplete_requisitions: string[] };
type ReportRef = { number: string; date: string; warehouse: string; products: number };
type MissingSpec = { number: string; date: string; product: string; quantity: number };
type Deviation = {
  number: string;
  date: string;
  warehouse: string;
  requisitions: string[];
  materials_differing: number;
  top: { material: string; unit: string; norm: number; fact: number }[];
};
type Result = {
  date_from: string;
  date_to: string;
  reports: number;
  reports_not_reflected: number;
  requisitions: number;
  costs: Costs | null;
  rows: Row[];
  reports_without_requisition: ReportRef[];
  lines_without_spec: MissingSpec[];
  report_deviations_total: number;
  report_deviations: Deviation[];
};

const THRESHOLDS = [0, 2, 5, 10, 25];
const SORTS = {
  money: { label: "отклонению в тенге", key: (row: Row) => Math.abs(row.diff_cost ?? 0) },
  pct: { label: "% отклонения", key: (row: Row) => (row.diff_pct === null ? -1 : Math.abs(row.diff_pct)) },
  diff: { label: "отклонению в единицах", key: (row: Row) => Math.abs(row.diff) },
  norm: { label: "объёму нормы", key: (row: Row) => row.norm },
};
type SortKey = keyof typeof SORTS;

function isoDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function qty(value: number) {
  return value.toLocaleString("ru-RU", { maximumFractionDigits: 3 });
}

function money(value: number) {
  return `${value.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₸`;
}

// Summary tiles are narrow: 74 040 693 ₸ -> 74,04 млн ₸.
function compactMoney(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1e6) return `${(value / 1e6).toLocaleString("ru-RU", { maximumFractionDigits: 2 })} млн ₸`;
  if (abs >= 1e3) return `${(value / 1e3).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} тыс. ₸`;
  return money(value);
}

const NOWRAP = { whiteSpace: "nowrap" } as const;

function signed(value: number, format: (value: number) => string) {
  return `${value > 0 ? "+" : ""}${format(value)}`;
}

function day(value: string) {
  return new Date(value).toLocaleDateString("ru-RU");
}

// A material without a norm but with a write-off is the strongest deviation.
function deviation(row: Row) {
  return row.diff_pct === null ? Infinity : Math.abs(row.diff_pct);
}

export function OneCReconciliation() {
  const today = new Date();
  const [period, setPeriod] = useState({ date_from: isoDate(new Date(today.getFullYear(), today.getMonth(), 1)), date_to: isoDate(today) });
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [threshold, setThreshold] = useState(5);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("money");

  async function run() {
    setLoading(true);
    setError("");
    try {
      // Documents are read from 1C for the whole period; this can take a while.
      const { data } = await apiClient.get<Result>("/integrations/1c/reconciliation", { params: period, timeout: 600000 });
      setResult(data);
      setWarehouse("");
    } catch (err) {
      setError(apiErrorMessage(err, "Сверка не выполнена."));
    } finally {
      setLoading(false);
    }
  }

  const warehouses = useMemo(() => [...new Set(result?.rows.map((row) => row.warehouse) ?? [])].sort((a, b) => a.localeCompare(b, "ru")), [result]);
  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (result?.rows ?? [])
      .filter((row) => !warehouse || row.warehouse === warehouse)
      .filter((row) => !needle || row.material.toLowerCase().includes(needle) || row.code.toLowerCase().includes(needle))
      .filter((row) => deviation(row) >= threshold)
      .sort((a, b) => SORTS[sort].key(b) - SORTS[sort].key(a) || a.material.localeCompare(b.material, "ru"));
  }, [result, warehouse, threshold, search, sort]);
  const deviating = useMemo(() => (result?.rows ?? []).filter((row) => deviation(row) >= 5).length, [result]);

  return <ConsoleShell title="Сверка списания сырья" subtitle="Норма по отчётам производства 1С против требований-накладных">
    <section className="editor-card">
      <p>
        Норма считается по проведённым отчётам производства за смену: выпуск (включая брак) умножается на состав спецификации из строки отчёта.
        Факт — проведённые требования-накладные по тому же складу сырья, отдельно по отчётам и по актам приёма-передачи.
        Данные читаются из 1С, в 1С ничего не записывается.
      </p>
      <div className="statistics-filters">
        <label>С даты<input type="date" value={period.date_from} onChange={(event) => setPeriod({ ...period, date_from: event.target.value })} /></label>
        <label>По дату<input type="date" value={period.date_to} onChange={(event) => setPeriod({ ...period, date_to: event.target.value })} /></label>
        <button type="button" disabled={loading || !period.date_from || !period.date_to} onClick={() => void run()}>{loading ? "Читаем документы 1С…" : "Сверить"}</button>
      </div>
      {loading && <p role="status">Получаем отчёты, требования и проводки за период. За месяц это 1–2 минуты.</p>}
      {error && <p className="error-text" role="alert">{error}</p>}
    </section>

    {result && <>
      <section className="statistics-summary">
        <article><small>Отчётов производства</small><strong>{result.reports}</strong></article>
        <article><small>Требований-накладных</small><strong>{result.requisitions}</strong></article>
        <article><small>Позиций сырья</small><strong>{result.rows.length}</strong></article>
        {result.costs && <>
          <article><small>Списано сырья на сумму</small><strong>{compactMoney(result.costs.fact)}</strong></article>
          <article><small>{result.costs.diff >= 0 ? "Перерасход против нормы" : "Экономия против нормы"}</small><strong>{signed(result.costs.diff, compactMoney)}</strong></article>
        </>}
        <article><small>Отклонение больше 5%</small><strong>{deviating}</strong></article>
        <article><small>Отчётов без требования</small><strong>{result.reports_without_requisition.length}</strong></article>
      </section>

      <section className="editor-card">
        <h2>Сырьё за {day(result.date_from)} – {day(result.date_to)}</h2>
        <div className="statistics-filters">
          <label>Склад<select value={warehouse} onChange={(event) => setWarehouse(event.target.value)}>
            <option value="">Все склады</option>
            {warehouses.map((name) => <option key={name} value={name}>{name}</option>)}
          </select></label>
          <label>Отклонение<select value={threshold} onChange={(event) => setThreshold(Number(event.target.value))}>
            {THRESHOLDS.map((value) => <option key={value} value={value}>{value ? `от ${value}%` : "все позиции"}</option>)}
          </select></label>
          <label>Сортировать по<select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
            {(Object.keys(SORTS) as SortKey[]).map((key) => <option key={key} value={key}>{SORTS[key].label}</option>)}
          </select></label>
          <label>Поиск<input value={search} placeholder="Название или код" onChange={(event) => setSearch(event.target.value)} /></label>
        </div>
        {rows.length === 0 ? <div className="empty-state">Нет позиций с таким отклонением.</div> : <div className="order-table-scroll"><table className="order-table">
          <thead><tr><th>Склад</th><th>Сырьё</th><th>Ед.</th><th>Норма</th><th>Списано</th><th>в т.ч. по актам</th><th>Отклонение</th><th>%</th>{result.costs && <><th>Цена</th><th>Списано, ₸</th><th>Отклонение, ₸</th></>}</tr></thead>
          <tbody>{rows.map((row) => <tr key={`${row.warehouse}|${row.code}|${row.material}`}>
            <td>{row.warehouse}</td>
            <td>{row.material}{row.code && <small> · {row.code}</small>}</td>
            <td>{row.unit}</td>
            <td>{qty(row.norm)}</td>
            <td>{qty(row.fact)}</td>
            <td>{row.fact_by_act ? qty(row.fact_by_act) : ""}</td>
            <td>{row.diff > 0 ? "+" : ""}{qty(row.diff)}</td>
            <td>{row.diff_pct === null ? "нет в норме" : `${row.diff_pct > 0 ? "+" : ""}${qty(row.diff_pct)}%`}</td>
            {result.costs && <>
              <td style={NOWRAP}>{row.price != null ? money(row.price) : "нет цены"}</td>
              <td style={NOWRAP}>{money(row.fact_cost ?? 0)}{row.zero_cost_qty ? <small> · {qty(row.zero_cost_qty)} {row.unit} без себестоимости</small> : null}</td>
              <td style={NOWRAP}>{row.diff_cost != null ? signed(row.diff_cost, money) : ""}</td>
            </>}
          </tr>)}</tbody>
        </table></div>}
        <p><small>Показано {rows.length} из {result.rows.length}. «Нет в норме» — сырьё списано (обычно по актам приёма-передачи), но не входит в спецификации выпущенной продукции; при сортировке по % такие позиции в конце.
          {result.costs && <> Цена — средняя себестоимость списания за период по проводкам 1С (по складу, иначе по материалу в целом); отклонение в тенге = отклонение в единицах × цена.
            «Нет цены» обычно у собственных полуфабрикатов: они списываются без себестоимости, а их сырьё уже учтено в отчётах об их выпуске.</>}</small></p>
      </section>

      {result.reports_without_requisition.length > 0 && <section className="editor-card">
        <h2>Отчёты производства без требования-накладной</h2>
        <p>Выпуск оформлен, а сырьё по нему не списано (проверено с запасом 7 дней после периода).</p>
        <div className="order-table-scroll"><table className="order-table">
          <thead><tr><th>Отчёт</th><th>Дата</th><th>Склад сырья</th><th>Строк продукции</th></tr></thead>
          <tbody>{result.reports_without_requisition.map((r) => <tr key={r.number}><td>{r.number}</td><td>{day(r.date)}</td><td>{r.warehouse}</td><td>{r.products}</td></tr>)}</tbody>
        </table></div>
      </section>}

      {result.report_deviations_total > 0 && <section className="editor-card">
        <h2>Требования, отличающиеся от своего отчёта · {result.report_deviations_total}</h2>
        <p>Требование создано на основании отчёта, но количества не совпадают с расчётом по спецификации больше чем на 1%. Обычно это ручная правка требования или отчёта после его создания.{result.report_deviations_total > result.report_deviations.length && ` Показаны первые ${result.report_deviations.length}.`}</p>
        <div className="order-table-scroll"><table className="order-table">
          <thead><tr><th>Отчёт</th><th>Дата</th><th>Склад сырья</th><th>Требование</th><th>Позиций с отличием</th><th>Наибольшие отличия (норма → списано)</th></tr></thead>
          <tbody>{result.report_deviations.map((d) => <tr key={d.number}>
            <td>{d.number}</td><td>{day(d.date)}</td><td>{d.warehouse}</td><td>{d.requisitions.join(", ")}</td><td>{d.materials_differing}</td>
            <td>{d.top.map((t) => `${t.material}: ${qty(t.norm)} → ${qty(t.fact)} ${t.unit}`).join("; ")}</td>
          </tr>)}</tbody>
        </table></div>
      </section>}

      {result.lines_without_spec.length > 0 && <section className="editor-card">
        <h2>Строки отчётов без спецификации · {result.lines_without_spec.length}</h2>
        <p>Для этих строк норму посчитать нельзя, поэтому они не входят в «Норму» выше.</p>
        <div className="order-table-scroll"><table className="order-table">
          <thead><tr><th>Отчёт</th><th>Дата</th><th>Продукция</th><th>Количество</th></tr></thead>
          <tbody>{result.lines_without_spec.map((l, index) => <tr key={`${l.number}-${index}`}><td>{l.number}</td><td>{day(l.date)}</td><td>{l.product}</td><td>{qty(l.quantity)}</td></tr>)}</tbody>
        </table></div>
      </section>}

      {result.costs && result.costs.incomplete_requisitions.length > 0 && <section className="editor-card">
        <h2>Требования без полной стоимости · {result.costs.incomplete_requisitions.length}</h2>
        <p>Проводки этих требований не совпали с их строками по количеству, поэтому их стоимость не учтена: {result.costs.incomplete_requisitions.join(", ")}.</p>
      </section>}

      {result.reports_not_reflected > 0 && <p><small>Отчётов с флагом «Не отражать в отчётах по сырью» исключено: {result.reports_not_reflected}.</small></p>}
    </>}
  </ConsoleShell>;
}
