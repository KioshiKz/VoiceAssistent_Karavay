import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { FolderOut } from "../api/types";
import { buildFolderTree, isDescendant, type FolderNode } from "../utils/folderTree";

interface FolderTreeProps {
  folders: FolderOut[];
  currentFolderId: string | null;
  onMove: (folderId: string, newParentId: string | null) => void;
}

function TreeNode({
  node,
  depth,
  currentFolderId,
  folders,
  onMove,
  dropTargetId,
  setDropTargetId,
}: {
  node: FolderNode;
  depth: number;
  currentFolderId: string | null;
  folders: FolderOut[];
  onMove: (folderId: string, newParentId: string | null) => void;
  dropTargetId: string | null;
  setDropTargetId: (id: string | null) => void;
}) {
  const navigate = useNavigate();
  const isActive = node.id === currentFolderId;
  const isDropTarget = dropTargetId === node.id;

  return (
    <>
      <div
        className={`folder-tree-node${isActive ? " active" : ""}${isDropTarget ? " drop-target" : ""}`}
        style={{ paddingLeft: 8 + depth * 14 }}
        draggable
        onDragStart={(e) => e.dataTransfer.setData("text/folder-id", node.id)}
        onDragOver={(e) => {
          e.preventDefault();
          setDropTargetId(node.id);
        }}
        onDragLeave={() => setDropTargetId(null)}
        onDrop={(e) => {
          e.preventDefault();
          setDropTargetId(null);
          const draggedId = e.dataTransfer.getData("text/folder-id");
          if (!draggedId || draggedId === node.id) return;
          if (isDescendant(folders, node.id, draggedId)) return;
          onMove(draggedId, node.id);
        }}
        onDoubleClick={() => navigate(`/files/${node.id}`)}
        onClick={() => navigate(`/files/${node.id}`)}
      >
        📁 {node.name}
      </div>
      {node.children.map((c) => (
        <TreeNode
          key={c.id}
          node={c}
          depth={depth + 1}
          currentFolderId={currentFolderId}
          folders={folders}
          onMove={onMove}
          dropTargetId={dropTargetId}
          setDropTargetId={setDropTargetId}
        />
      ))}
    </>
  );
}

export function FolderTree({ folders, currentFolderId, onMove }: FolderTreeProps) {
  const tree = useMemo(() => buildFolderTree(folders), [folders]);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  const navigate = useNavigate();

  return (
    <div
      className="folder-tree"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const draggedId = e.dataTransfer.getData("text/folder-id");
        if (draggedId) onMove(draggedId, null);
      }}
    >
      <div className="folder-tree-node" onClick={() => navigate("/files")}>
        🏠 Корень
      </div>
      {tree.map((n) => (
        <TreeNode
          key={n.id}
          node={n}
          depth={0}
          currentFolderId={currentFolderId}
          folders={folders}
          onMove={onMove}
          dropTargetId={dropTargetId}
          setDropTargetId={setDropTargetId}
        />
      ))}
    </div>
  );
}
