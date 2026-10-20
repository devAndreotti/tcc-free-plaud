import { useEffect, useRef, useState, type ComponentType } from 'react';
import {
  AskIcon,
  BarChartIcon,
  CheckIcon,
  ChevronsUpDownIcon,
  CodeIcon,
  ContrastIcon,
  FolderIcon,
  LayersIcon,
  MicIcon,
  NoteIcon,
  PanelLeftIcon,
  PlusIcon,
  SettingsIcon,
  SlidersIcon,
  StarsIcon,
  VaultIcon,
} from './Icons';
import type { SettingsTab } from './SettingsModal';
import { useQueueContext } from '../hooks/useQueueContext';
import { useVaults } from '../hooks/useVaults';
import { vaultMeta } from '../lib/vaultVisuals';
import VaultDialog from './VaultDialog';
import { VaultGlyph } from './VaultGlyph';
import { useCorpusHealth } from '../hooks/useCorpusHealth';
import { readMigratedItem } from '../services/localStorageMigration';

export type WorkspaceView = 'chat' | 'notes' | 'benchmark' | 'queue';

interface SidebarProps {
  activeView: WorkspaceView;
  onNavigate: (view: WorkspaceView) => void;
  onOpenSettings: (tab?: SettingsTab) => void;
  /** Muda quando o modal de configurações fecha, para recarregar a saúde do corpus. */
  healthKey: unknown;
}

type IconType = ComponentType<{ size?: number; className?: string }>;

const NAV: { view: WorkspaceView; label: string; icon: IconType; id: string }[] = [
  { view: 'chat', label: 'Perguntar', icon: AskIcon, id: 'btn-sidebar-chat' },
  { view: 'notes', label: 'Notas', icon: NoteIcon, id: 'btn-sidebar-notes' },
  { view: 'queue', label: 'Fila', icon: LayersIcon, id: 'btn-sidebar-queue' },
  { view: 'benchmark', label: 'Benchmark', icon: BarChartIcon, id: 'btn-sidebar-benchmark' },
];

const SECTIONS: { tab: SettingsTab; label: string; icon: IconType }[] = [
  { tab: 'geral', label: 'Geral', icon: SlidersIcon },
  { tab: 'vaults', label: 'Vaults', icon: VaultIcon },
  { tab: 'ia', label: 'IA', icon: StarsIcon },
  { tab: 'voz', label: 'Voz', icon: MicIcon },
  { tab: 'avancado', label: 'Avançado', icon: CodeIcon },
  { tab: 'aparencia', label: 'Aparência', icon: ContrastIcon },
];

const COLLAPSED_KEY = 'escolio:sidebar-collapsed';
const LEGACY_COLLAPSED_KEY = 'free-plaud:sidebar-collapsed';

const readCollapsed = () => readMigratedItem(COLLAPSED_KEY, LEGACY_COLLAPSED_KEY) !== 'false';

const folderName = (path: string | null | undefined) => {
  if (!path) return null;
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
};

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('pt-BR')} ${n === 1 ? one : many}`;

const Sidebar = ({ activeView, onNavigate, onOpenSettings, healthKey }: SidebarProps) => {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const { job, watcherActive, folderPath } = useQueueContext();
  const { vaults, active, select } = useVaults();
  const [menuOpen, setMenuOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const switchRef = useRef<HTMLDivElement>(null);

  // Menu de vaults fecha ao clicar fora ou com Esc.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (event: MouseEvent) => {
      if (!switchRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);
  const health = useCorpusHealth(healthKey);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSED_KEY, String(collapsed));
    } catch {
      // Sem persistência: vale só para esta sessão.
    }
  }, [collapsed]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && (event.key === 'b' || event.key === 'B')) {
        event.preventDefault();
        setCollapsed((prev) => !prev);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const running = job?.status === 'running';
  const progress = job?.progress;
  const queuePercent = running && progress && progress.total_found > 0
    ? Math.round((progress.processed_count / progress.total_found) * 100)
    : null;

  const toggleLabel = collapsed ? 'Expandir menu' : 'Recolher menu';
  const vaultName = folderName(folderPath);
  const healthStatus = health?.status ?? 'unknown';
  const healthText = !health
    ? 'Verificando corpus'
    : health.errorCount > 0
      ? plural(health.errorCount, 'erro', 'erros')
      : health.warningCount > 0
        ? plural(health.warningCount, 'aviso', 'avisos')
        : 'saudável';

  return (
    <>
    <aside className={`sb${collapsed ? ' sb--collapsed' : ''}`} aria-label="Navegação">
      <div className="sb__head">
        <span className="sb__mark" aria-hidden="true">ES</span>
        <span className="sb__name">Escólio</span>
        <button
          type="button"
          id="btn-sidebar-toggle"
          className="sb__item sb__toggle"
          aria-label={toggleLabel}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed((prev) => !prev)}
        >
          <PanelLeftIcon />
          <span className="sb__tip">{toggleLabel}<small>Ctrl B</small></span>
        </button>
      </div>

      {/* Seletor da vault ativa: cartão com nome e contagens; recolhida, só o ícone. */}
      <div className="sb__vault-switch" ref={switchRef}>
        <button
          type="button"
          id="btn-vault-switcher"
          className="sb__vault"
          aria-expanded={menuOpen}
          aria-label={`Vault ativa: ${active?.name ?? 'nenhuma'}. Trocar vault`}
          onClick={() => setMenuOpen((prev) => !prev)}
        >
          {active ? (
            <VaultGlyph icon={active.icon} color={active.color} size={17} />
          ) : (
            <span className="vault-glyph vault-glyph--slate" aria-hidden="true">
              <FolderIcon size={17} />
            </span>
          )}
          <span className="sb__vault-text">
            <span className="sb__vault-name">{active?.name ?? 'Carregando vaults…'}</span>
            {active && <span className="sb__vault-meta mono">{vaultMeta(active)}</span>}
          </span>
          <ChevronsUpDownIcon size={16} className="sb__vault-chevron" />
          <span className="sb__tip">{active?.name ?? 'Vault'}<small>trocar vault</small></span>
        </button>
        {menuOpen && (
          <div className="sb__vault-menu" role="group" aria-label="Vaults">
            <div className="sb__vault-menu-head" aria-hidden="true">Trocar de vault</div>
            {vaults.map((vault) => (
              <button
                key={vault.id}
                type="button"
                aria-pressed={vault.id === active?.id}
                className="sb__vault-item"
                onClick={() => {
                  setMenuOpen(false);
                  if (vault.id !== active?.id) void select(vault.id);
                }}
              >
                <VaultGlyph icon={vault.icon} color={vault.color} size={15} />
                <span className="sb__vault-item-text">
                  <span>{vault.name}</span>
                  <small className="mono">{vaultMeta(vault)}</small>
                </span>
                {vault.id === active?.id && <CheckIcon size={16} className="sb__vault-check" />}
              </button>
            ))}
            <div className="sb__sep" role="separator" />
            <button
              type="button"
              className="sb__vault-item"
              onClick={() => {
                setMenuOpen(false);
                setCreating(true);
              }}
            >
              <PlusIcon size={16} />
              <span>Nova vault</span>
            </button>
            <button
              type="button"
              className="sb__vault-item"
              onClick={() => {
                setMenuOpen(false);
                onOpenSettings('vaults');
              }}
            >
              <VaultIcon size={16} />
              <span>Gerenciar vaults</span>
            </button>
          </div>
        )}
      </div>

      <nav className="sb__nav" aria-label="Navegação principal">
        {NAV.map(({ view, label, icon: ItemIcon, id }) => {
          const active = activeView === view;
          const isQueue = view === 'queue';
          return (
            <button
              key={view}
              id={id}
              type="button"
              className={`sb__item${active ? ' sb__item--active' : ''}`}
              aria-current={active ? 'page' : undefined}
              onClick={() => onNavigate(view)}
            >
              <ItemIcon />
              <span className="sb__label">{label}</span>
              {isQueue && queuePercent !== null && <span className="sb__meta mono">{queuePercent}%</span>}
              {isQueue && running && <span className="sb__pip" aria-hidden="true" />}
              <span className="sb__tip">
                {label}
                {isQueue && queuePercent !== null && <small>indexando · {queuePercent}%</small>}
              </span>
            </button>
          );
        })}

        <div className="sb__sep" role="separator" />

        <div className="sb__settings">
          <button
            type="button"
            id="btn-sidebar-settings"
            className="sb__item"
            aria-haspopup="dialog"
            onClick={() => onOpenSettings()}
          >
            <SettingsIcon size={18} />
            <span className="sb__label">Configurações</span>
            <span className="sb__tip">Configurações</span>
          </button>
          <div className="sb__flyout" role="group" aria-label="Seções de configuração">
            <div className="sb__flyout-head">
              <span>Configurações</span>
            </div>
            {SECTIONS.map(({ tab, label, icon: SectionIcon }) => (
              <button
                key={tab}
                type="button"
                className="sb__fly-item"
                onClick={() => onOpenSettings(tab)}
              >
                <SectionIcon size={16} />
                <span>{label}</span>
                {tab === 'geral' && health && healthStatus !== 'ok' && (
                  <em className={`sb__fly-note sb__fly-note--${healthStatus}`}>{healthText}</em>
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <div className="sb__spacer" />

      <button
        type="button"
        className={`sb__health sb__health--${healthStatus}`}
        onClick={() => onOpenSettings('geral')}
        aria-label={`Corpus: ${healthText}. Abrir diagnóstico`}
      >
        <span className="sb__health-ring" aria-hidden="true" />
        <span className="sb__health-row">
          <span className="sb__dot" aria-hidden="true" />
          <b>Corpus</b>
          <span className="sb__health-state">{healthText}</span>
        </span>
        {health && (
          <span className="sb__health-sub mono">
            {plural(health.notes, 'nota', 'notas')} · {plural(health.chunks, 'trecho', 'trechos')}
          </span>
        )}
        {vaultName && (
          <span className="sb__health-vault">
            <FolderIcon size={14} />
            <span className="sb__health-vault-name">{vaultName}</span>
            <span className="sb__health-watch">
              <span className={`sb__dot${watcherActive ? ' sb__dot--ok' : ' sb__dot--off'}`} aria-hidden="true" />
              {watcherActive ? 'monitorando' : 'parado'}
            </span>
          </span>
        )}
        <span className="sb__tip">Corpus: {healthText}<small>abrir diagnóstico</small></span>
      </button>
    </aside>
    {creating && <VaultDialog onClose={() => setCreating(false)} />}
    </>
  );
};

export default Sidebar;
