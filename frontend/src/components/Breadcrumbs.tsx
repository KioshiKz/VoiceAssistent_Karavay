import { Link } from "react-router-dom";
import type { BreadcrumbOut } from "../api/types";

export function Breadcrumbs({ items }: { items: BreadcrumbOut[] }) {
  return (
    <div className="breadcrumbs">
      <Link to="/files">Файлы</Link>
      {items.map((b) => (
        <span key={b.id} style={{ display: "flex", gap: 6 }}>
          <span className="sep">/</span>
          <Link to={`/files/${b.id}`}>{b.name}</Link>
        </span>
      ))}
    </div>
  );
}
