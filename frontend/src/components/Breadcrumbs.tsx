import { Link } from "react-router-dom";
import type { BreadcrumbOut } from "../api/types";

export function Breadcrumbs({ items }: { items: BreadcrumbOut[] }) {
  return (
    <div className="breadcrumbs">
      <Link to="/files">Файлы</Link>
      {items.map((item) => (
        <span key={item.id} style={{ display: "flex", gap: 6 }}>
          <span className="sep">/</span>
          <Link to={`/files/${item.id}`}>{item.name}</Link>
        </span>
      ))}
    </div>
  );
}
