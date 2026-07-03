import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ordersApi, productsApi } from "../api/endpoints";
import type { CurrentOrderOut, OrderLineOut, ProductOut } from "../api/types";

function MatchResolver({ line, onMatched }: { line: OrderLineOut; onMatched: () => void }) {
  const [query, setQuery] = useState(line.product_name_raw);
  const [results, setResults] = useState<ProductOut[]>([]);

  useEffect(() => {
    const handle = setTimeout(() => {
      productsApi.search(query).then(setResults);
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Найти продукцию..." />
      <select
        onChange={async (e) => {
          if (!e.target.value) return;
          await ordersApi.match(line.id, e.target.value);
          onMatched();
        }}
        defaultValue=""
      >
        <option value="" disabled>
          Выбрать
        </option>
        {results.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export function CurrentOrder() {
  const navigate = useNavigate();
  const [order, setOrder] = useState<CurrentOrderOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    ordersApi
      .current()
      .then(setOrder)
      .catch(() => setError("Заявки ещё не загружены."));
  }

  useEffect(reload, []);

  return (
    <div className="editor-page" style={{ maxWidth: 900 }}>
      <Link to="/">← Главная</Link>
      <h2>Текущая заявка</h2>

      {error && <p style={{ color: "#888" }}>{error}</p>}

      {order && (
        <>
          <p style={{ color: "#888" }}>Дата исполнения: {order.execution_date}</p>
          <table className="order-table">
            <thead>
              <tr>
                <th>Продукция</th>
                <th>Количество</th>
                <th>Время</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {order.lines.map((line) => (
                <tr
                  key={line.id}
                  style={{ cursor: line.match_status === "matched" ? "pointer" : "default" }}
                  onClick={() => {
                    if (line.match_status === "matched") {
                      navigate(`/orders/current/${line.id}/execute`);
                    }
                  }}
                >
                  <td>{line.product_name_raw}</td>
                  <td>{line.quantity}</td>
                  <td>{line.due_time.slice(0, 5)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {line.match_status === "matched" ? (
                      <span className="badge matched">исполнить →</span>
                    ) : (
                      <MatchResolver line={line} onMatched={reload} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
