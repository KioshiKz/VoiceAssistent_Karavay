import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Folder, Home } from "lucide-react";
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
        draggable={node.parent_id !== null}
        onDragStart={(event) => event.dataTransfer.setData("text/folder-id", node.id)}
        onDragOver={(event) => {
          event.preventDefault();
          setDropTargetId(node.id);
        }}
        onDragLeave={() => setDropTargetId(null)}
        onDrop={(event) => {
          event.preventDefault();
          setDropTargetId(null);
          const draggedId = event.dataTransfer.getData("text/folder-id");
          if (!draggedId || draggedId === node.id) return;
          if (isDescendant(folders, node.id, draggedId)) return;
          onMove(draggedId, node.id);
        }}
        onClick={() => navigate(`/files/${node.id}`)}
      >
        <Folder size={16} />
        <span>{node.name}</span>
      </div>
      {node.children.map((child) => (
        <TreeNode
          key={child.id}
          node={child}
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
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const draggedId = event.dataTransfer.getData("text/folder-id");
        if (draggedId) onMove(draggedId, null);
      }}
    >
      <div className="folder-tree-heading">
        <h2>Дерево</h2>
      </div>
      <div className={`folder-tree-node${currentFolderId ? "" : " active"}`} onClick={() => navigate("/files")}>
        <Home size={16} />
        <span>Корень</span>
      </div>
      {tree.map((node) => (
        <TreeNode
          key={node.id}
          node={node}
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
