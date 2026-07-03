import type { FolderOut } from "../api/types";

export interface FolderNode extends FolderOut {
  children: FolderNode[];
}

export function buildFolderTree(folders: FolderOut[]): FolderNode[] {
  const nodes = new Map<string, FolderNode>();
  folders.forEach((f) => nodes.set(f.id, { ...f, children: [] }));
  const roots: FolderNode[] = [];
  nodes.forEach((node) => {
    if (node.parent_id && nodes.has(node.parent_id)) {
      nodes.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

export function isDescendant(folders: FolderOut[], candidateId: string, ancestorId: string): boolean {
  let current = folders.find((f) => f.id === candidateId);
  while (current?.parent_id) {
    if (current.parent_id === ancestorId) return true;
    current = folders.find((f) => f.id === current!.parent_id);
  }
  return false;
}
