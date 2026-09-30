const TYPE_LABEL: Record<string, string> = {
  md: 'Markdown',
  markdown: 'Markdown',
  pdf: 'PDF',
  txt: 'Texto',
  audio: 'Áudio transcrito',
};

export const typeLabel = (type: string | null | undefined) =>
  (type && TYPE_LABEL[type.toLowerCase()]) ?? (type ? type.toUpperCase() : 'Nota');

export const formatDate = (iso: string | null | undefined, withYear = true) => {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('pt-BR', withYear ? undefined : { day: '2-digit', month: '2-digit' });
};

const splitPath = (path: string) => path.split(/[\\/]/).filter(Boolean);

/** Pastas em comum a todos os caminhos: a raiz do vault, sem precisar perguntar ao backend. */
export const commonRoot = (paths: string[]): string[] => {
  const dirs = paths.filter(Boolean).map((p) => splitPath(p).slice(0, -1));
  if (dirs.length === 0) return [];
  const root: string[] = [];
  for (let i = 0; i < dirs[0].length; i += 1) {
    const part = dirs[0][i];
    if (dirs.every((d) => d[i] === part)) root.push(part);
    else break;
  }
  return root;
};

/** Caminho relativo à raiz, quebrado em partes (o último item é o nome do arquivo). */
export const relativeParts = (path: string | null | undefined, root: string[]): string[] => {
  if (!path) return [];
  const parts = splitPath(path);
  const same = root.every((part, i) => parts[i] === part);
  return same ? parts.slice(root.length) : parts;
};
