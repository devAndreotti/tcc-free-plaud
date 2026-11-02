import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Sidebar from './Sidebar';

vi.mock('../hooks/useQueueContext', () => ({
  useQueueContext: () => ({
    job: { status: 'running', progress: { processed_count: 29, total_found: 50 } },
    watcherActive: true,
    folderPath: String.raw`C:\Vault\Obsidian-Core`,
  }),
}));

const obsidian = { id: 'obsidian', name: 'Obsidian', icon: 'notes', color: 'violet', folders: [], embedding_model: null, created_at: '', sqlite_path: null, vector_store_dir: null, note_count: 42 };
vi.mock('../hooks/useVaults', () => ({
  useVaults: () => ({
    vaults: [obsidian],
    active: obsidian,
    version: 0,
    refresh: vi.fn(),
    select: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  }),
}));

vi.mock('../hooks/useCorpusHealth', () => ({
  useCorpusHealth: () => ({ notes: 668, chunks: 4195, status: 'error', errorCount: 1, warningCount: 0 }),
}));

// jsdom não tem largura real nem matchMedia: simulamos os dois.
const LARGURA_PADRAO = 1024;
let listeners: Array<(event: MediaQueryListEvent) => void> = [];

const setWidth = (width: number) => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: width });
};

// Como o navegador: o listener só dispara quando a faixa max-width: 899px muda de lado.
const resize = (width: number) => {
  const before = window.innerWidth < 900;
  setWidth(width);
  if ((width < 900) === before) return;
  act(() => {
    listeners.forEach((fn) => fn({ matches: width < 900 } as MediaQueryListEvent));
  });
};

const sidebarEl = (container: HTMLElement) => container.querySelector('.sb');

describe('Sidebar', () => {
  beforeEach(() => {
    window.localStorage.clear();
    listeners = [];
    setWidth(LARGURA_PADRAO);
    window.matchMedia = vi.fn().mockImplementation(() => ({
      get matches() {
        return window.innerWidth < 900;
      },
      media: '(max-width: 899px)',
      addEventListener: (_: string, fn: (event: MediaQueryListEvent) => void) => listeners.push(fn),
      removeEventListener: (_: string, fn: (event: MediaQueryListEvent) => void) => {
        listeners = listeners.filter((item) => item !== fn);
      },
    })) as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    cleanup();
  });

  it('sem escolha salva, abre em janela larga e recolhe em janela estreita', () => {
    const { container, unmount } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(false);
    unmount();

    setWidth(800);
    const narrow = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(sidebarEl(narrow.container)?.classList.contains('sb--collapsed')).toBe(true);
  });

  it('escolha salva vale em janela larga, nas duas direções', () => {
    window.localStorage.setItem('escolio:sidebar-collapsed', 'true');
    const recolhida = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(sidebarEl(recolhida.container)?.classList.contains('sb--collapsed')).toBe(true);
    recolhida.unmount();

    window.localStorage.setItem('escolio:sidebar-collapsed', 'false');
    const aberta = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(sidebarEl(aberta.container)?.classList.contains('sb--collapsed')).toBe(false);
  });

  it('em janela estreita recolhe sozinha sem apagar a escolha salva, e volta ao alargar', () => {
    window.localStorage.setItem('escolio:sidebar-collapsed', 'false');
    setWidth(800);
    const { container } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(true);
    expect(window.localStorage.getItem('escolio:sidebar-collapsed')).toBe('false');

    resize(1024);
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(false);
    expect(window.localStorage.getItem('escolio:sidebar-collapsed')).toBe('false');
  });

  it('expandir em janela estreita vale até a próxima mudança de largura', async () => {
    const user = userEvent.setup();
    setWidth(800);
    const { container } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(true);

    await user.click(screen.getByRole('button', { name: 'Expandir menu' }));
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(false);

    // Continua estreita: sem mudança de faixa, a expansão se mantém.
    resize(820);
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(false);

    // Alarga e depois estreita de novo: a expansão manual já não vale.
    resize(1024);
    resize(800);
    expect(sidebarEl(container)?.classList.contains('sb--collapsed')).toBe(true);
  });

  it('começa recolhida em janela estreita e expande pelo botão, lembrando a escolha', async () => {
    const user = userEvent.setup();
    setWidth(800);
    const { container } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(container.querySelector('.sb')?.classList.contains('sb--collapsed')).toBe(true);

    await user.click(screen.getByRole('button', { name: 'Expandir menu' }));

    expect(container.querySelector('.sb')?.classList.contains('sb--collapsed')).toBe(false);
    expect(window.localStorage.getItem('escolio:sidebar-collapsed')).toBe('false');
  });

  it('migra a preferência antiga free-plaud:sidebar-collapsed', () => {
    window.localStorage.setItem('free-plaud:sidebar-collapsed', 'false');
    const { container } = render(
      <Sidebar activeView="chat" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />
    );
    expect(container.querySelector('.sb')?.classList.contains('sb--collapsed')).toBe(false);
    expect(window.localStorage.getItem('escolio:sidebar-collapsed')).toBe('false');
  });

  it('navega e abre Configurações direto na seção escolhida', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const onOpenSettings = vi.fn();
    render(<Sidebar activeView="chat" onNavigate={onNavigate} onOpenSettings={onOpenSettings} healthKey={0} />);
    expect(document.querySelector('[role="menu"], [role="menuitem"]')).toBeNull();

    await user.click(screen.getByRole('button', { name: /Notas/ }));
    expect(onNavigate).toHaveBeenCalledWith('notes');

    await user.click(screen.getByRole('button', { name: /Voz/ }));
    expect(onOpenSettings).toHaveBeenCalledWith('voz');
  });

  it('mostra progresso da fila, saúde do corpus e vault monitorado', () => {
    render(<Sidebar activeView="queue" onNavigate={vi.fn()} onOpenSettings={vi.fn()} healthKey={0} />);

    expect(screen.getAllByText('58%').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Corpus: 1 erro/ })).toBeTruthy();
    expect(screen.getByText('668 notas · 4.195 trechos')).toBeTruthy();
    expect(screen.getByText('Obsidian-Core')).toBeTruthy();
    expect(screen.getByText('monitorando')).toBeTruthy();
  });
});
