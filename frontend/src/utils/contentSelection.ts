export type ContentItemKind = "ingredient" | "product" | "event";

export interface ContentSelectionItem {
  kind: ContentItemKind;
  id: string;
  name: string;
  isActive: boolean;
}

export function contentItemKey(item: Pick<ContentSelectionItem, "kind" | "id">) {
  return `${item.kind}:${item.id}`;
}
