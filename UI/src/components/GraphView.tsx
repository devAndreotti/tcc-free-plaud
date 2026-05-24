/**
 * GraphView.tsx
 * ──────────────────────────────────────────────────────────────
 * Tela de visualização dos arquivos Markdown do Vault como nós.
 * Consome VaultContext para obter os dados escaneados.
 *
 * Estados visuais:
 *   1. Vault não configurado  → instrução para ir às Configurações
 *   2. Escaneando             → skeleton loader animado
 *   3. Vazio (nenhum .md)    → estado vazio com mensagem
 *   4. Populado              → grade de cards com busca por nome
 * ──────────────────────────────────────────────────────────────
 */

import { useState, useMemo } from 'react';
import { useVaultContext } from '../contexts/VaultContext';
import type { MarkdownNode } from '../hooks/useVault';

// ─── Ícone de arquivo Markdown (SVG inline) ─────────────────────────────────
function MarkdownIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="12" y2="13" />
      <polyline points="10 11 10 17" />
      <polyline points="14 13 16 11 18 13" />
    </svg>
  );
}

// ─── Ícone de pasta vazia ────────────────────────────────────────────────────
function FolderEmptyIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  );
}

// ─── Ícone de configurações ──────────────────────────────────────────────────
function SettingsIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

// ─── Ícone de busca ──────────────────────────────────────────────────────────
function SearchIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

// ─── Ícone de atualizar ──────────────────────────────────────────────────────
function RefreshIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

// ─── Utilitário: formata tamanho em bytes para leitura humana ────────────────
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─── Utilitário: formata data ISO para exibição ──────────────────────────────
function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

// ─── Card de nó individual ───────────────────────────────────────────────────
function NodeCard({ node }: { node: MarkdownNode }) {
  return (
    <article
      className="graph-node-card"
      role="listitem"
      aria-label={`Arquivo: ${node.name}`}
    >
      <div className="graph-node-card__icon" aria-hidden="true">
        <MarkdownIcon />
      </div>
      <div className="graph-node-card__body">
        <span className="graph-node-card__name" title={node.name}>
          {node.name}
        </span>
        <span className="graph-node-card__path" title={node.path}>
          {node.path || '/'}
        </span>
        <div className="graph-node-card__meta">
          <span>{formatBytes(node.size)}</span>
          <span className="graph-node-card__meta-sep" aria-hidden="true">·</span>
          <span>{formatDate(node.modified)}</span>
        </div>
      </div>
    </article>
  );
}

// ─── Skeleton de carregamento ────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="graph-node-card graph-node-card--skeleton" aria-hidden="true">
      <div className="graph-node-card__icon skeleton-box" />
      <div className="graph-node-card__body">
        <div className="skeleton-box skeleton-box--name" />
        <div className="skeleton-box skeleton-box--path" />
        <div className="skeleton-box skeleton-box--meta" />
      </div>
    </div>
  );
}

// ─── Componente principal ────────────────────────────────────────────────────
interface GraphViewProps {
  /** Callback para abrir o modal de configurações */
  onOpenSettings: () => void;
}

const GraphView = ({ onOpenSettings }: GraphViewProps) => {
  const { vaultPath, nodes, isScanning, lastScanAt, rescanVault } =
    useVaultContext();

  const [query, setQuery] = useState('');

  // Filtra nós pelo texto de busca (case-insensitive)
  const filteredNodes = useMemo(() => {
    if (!query.trim()) return nodes;
    const q = query.toLowerCase();
    return nodes.filter(
      (n) =>
        n.name.toLowerCase().includes(q) ||
        n.path.toLowerCase().includes(q)
    );
  }, [nodes, query]);

  // ── Estado 1: Vault não configurado ──────────────────────────────────────
  if (!vaultPath) {
    return (
      <div className="graph-view" id="graph-view">
        <div className="graph-empty-state" role="status">
          <div className="graph-empty-state__icon">
            <SettingsIcon />
          </div>
          <h2 className="graph-empty-state__title">Nenhum Vault configurado</h2>
          <p className="graph-empty-state__description">
            Selecione uma pasta nas Configurações para visualizar os arquivos
            Markdown como nós no grafo.
          </p>
          <button
            id="btn-graph-open-settings"
            type="button"
            className="graph-empty-state__action"
            onClick={onOpenSettings}
          >
            <SettingsIcon />
            Abrir Configurações
          </button>
        </div>
      </div>
    );
  }

  // ── Estado 2: Escaneando (skeleton) ──────────────────────────────────────
  if (isScanning) {
    return (
      <div className="graph-view" id="graph-view">
        <div className="graph-toolbar">
          <div className="graph-toolbar__info">
            <span className="graph-toolbar__vault-path" title={vaultPath}>
              {vaultPath}
            </span>
            <span className="graph-toolbar__scanning">Escaneando…</span>
          </div>
        </div>
        <div
          className="graph-grid"
          role="list"
          aria-label="Arquivos Markdown"
          aria-busy="true"
        >
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  // ── Estado 3: Vazio (nenhum .md encontrado) ───────────────────────────────
  if (nodes.length === 0) {
    return (
      <div className="graph-view" id="graph-view">
        <div className="graph-toolbar">
          <span className="graph-toolbar__vault-path" title={vaultPath}>
            {vaultPath}
          </span>
          <button
            id="btn-graph-rescan-empty"
            type="button"
            className="graph-toolbar__rescan"
            onClick={rescanVault}
            aria-label="Reescanear vault"
          >
            <RefreshIcon />
            Atualizar
          </button>
        </div>
        <div className="graph-empty-state" role="status">
          <div className="graph-empty-state__icon">
            <FolderEmptyIcon />
          </div>
          <h2 className="graph-empty-state__title">Nenhum arquivo Markdown</h2>
          <p className="graph-empty-state__description">
            Nenhum arquivo <code>.md</code> foi encontrado em{' '}
            <strong>{vaultPath}</strong>. Verifique se a pasta correta foi
            selecionada.
          </p>
        </div>
      </div>
    );
  }

  // ── Estado 4: Populado ───────────────────────────────────────────────────
  return (
    <div className="graph-view" id="graph-view">
      {/* Barra de ferramentas */}
      <div className="graph-toolbar">
        <div className="graph-toolbar__info">
          <span className="graph-toolbar__vault-path" title={vaultPath}>
            {vaultPath}
          </span>
          {lastScanAt && (
            <span className="graph-toolbar__scan-time">
              Atualizado às{' '}
              {lastScanAt.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          )}
        </div>

        <div className="graph-toolbar__actions">
          {/* Campo de busca por nome */}
          <div className="graph-search" role="search">
            <span className="graph-search__icon" aria-hidden="true">
              <SearchIcon />
            </span>
            <input
              id="input-graph-search"
              type="search"
              className="graph-search__input"
              placeholder="Buscar arquivo…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Buscar arquivos Markdown"
            />
          </div>

          {/* Botão de reescanear */}
          <button
            id="btn-graph-rescan"
            type="button"
            className="graph-toolbar__rescan"
            onClick={rescanVault}
            disabled={isScanning}
            aria-label="Reescanear vault"
          >
            <RefreshIcon />
            Atualizar
          </button>
        </div>
      </div>

      {/* Contador de resultados */}
      <p className="graph-count" aria-live="polite">
        {filteredNodes.length === nodes.length
          ? `${nodes.length} arquivo${nodes.length !== 1 ? 's' : ''} encontrado${nodes.length !== 1 ? 's' : ''}`
          : `${filteredNodes.length} de ${nodes.length} arquivo${nodes.length !== 1 ? 's' : ''}`}
      </p>

      {/* Grade de nós */}
      {filteredNodes.length > 0 ? (
        <div
          className="graph-grid"
          role="list"
          aria-label="Arquivos Markdown do Vault"
        >
          {filteredNodes.map((node) => (
            <NodeCard key={node.id} node={node} />
          ))}
        </div>
      ) : (
        <div className="graph-no-results" role="status">
          Nenhum arquivo corresponde a{' '}
          <strong>&quot;{query}&quot;</strong>.
        </div>
      )}
    </div>
  );
};

export default GraphView;
