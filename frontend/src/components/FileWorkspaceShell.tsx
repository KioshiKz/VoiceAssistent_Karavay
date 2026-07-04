import { useCallback, useEffect, useState, type ReactNode } from "react";
import { foldersApi } from "../api/endpoints";
import type { FolderOut } from "../api/types";
import { ConsoleShell } from "./ConsoleShell";
import { FolderTree } from "./FolderTree";

interface FileWorkspaceShellProps {
  title: string;
  subtitle?: string;
  currentFolderId: string | null;
  children: ReactNode;
  actions?: ReactNode;
}

export function FileWorkspaceShell({
  title,
  subtitle,
  currentFolderId,
  children,
  actions,
}: FileWorkspaceShellProps) {
  const [folders, setFolders] = useState<FolderOut[]>([]);

  const reloadTree = useCallback(() => {
    foldersApi.tree().then(setFolders);
  }, []);

  useEffect(() => {
    reloadTree();
  }, [reloadTree]);

  async function handleMove(folderId: string, newParentId: string | null) {
    await foldersApi.move(folderId, newParentId);
    reloadTree();
  }

  return (
    <ConsoleShell title={title} subtitle={subtitle} actions={actions}>
      <div className="file-manager-shell">
        <FolderTree folders={folders} currentFolderId={currentFolderId} onMove={handleMove} />
        <section className="folder-content-panel">{children}</section>
      </div>
    </ConsoleShell>
  );
}
