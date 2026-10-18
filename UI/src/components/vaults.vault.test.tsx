import { act, cleanup, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VaultsProvider, CORPUS_CHANGED_EVENT } from '../contexts/VaultsContext';
import { OPEN_VAULT_MENU_EVENT } from '../contexts/VaultsContextObject';
import { useIndexJob } from '../hooks/useIndexJob';
import { useVaults } from '../hooks/useVaults';
import { bridge, type Vault, type VaultList } from '../services/bridge';
import Sidebar from './Sidebar';
import VaultDialog from './VaultDialog';
import VaultsTab from './VaultsTab';
import WelcomeScreen from './WelcomeScreen';

vi.mock('../hooks/useQueueContext', () => ({
  useQueueContext: () => ({ job: null, watcherActive: false, folderPath: '' }),
}));
vi.mock('../hooks/useCorpusHealth', () => ({
  useCorpusHealth: () => null,
  notifyCorpusChanged: () => window.dispatchEvent(new Event('escolio:corpus-changed')),
}));

const base = { embedding_model: 'chroma-default', created_at: '2026-10-18T12:00:00-03:00', sqlite_path: null, vector_store_dir: null };
const OBSIDIAN: Vault = {
  ...base,
  id: 'obsidian',
  name: 'Obsidian',
  icon: 'notes',
  color: 'violet',
  folders: [String.raw`C:\Obsidian`],
  note_count: 42,
  roots: [
    { root: String.raw`C:\Obsidian\Area de TI`, notes_count: 40 },
    { root: String.raw`C:\Obsidian\Windows`, notes_count: 2 },
  ],
};
const CULINARIA: Vault = { ...base, id: 'culinaria', name: 'Culinária', icon: 'code', color: 'rose', folders: [], note_count: 7, roots: [] };
const LIST: VaultList = { active: 'obsidian', vaults: [OBSIDIAN, CULINARIA] };

const renderWithVaults = (ui: React.ReactNode) => render(<VaultsProvider>{ui}</VaultsProvider>);

describe('vaults: seletor, criação e aba Vaults', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('vault: seletor lista as vaults e trocar chama selectVault, recarrega a lista e avisa o app', async () => {
    const listSpy = vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const selectSpy = vi.spyOn(bridge, 'selectVault').mockResolvedValue({ ok: true, active: 'culinaria' });
    const changed = vi.fn();
    window.addEventListener(CORPUS_CHANGED_EVENT, changed);
    const user = userEvent.setup();

    renderWithVaults(
      <Sidebar activeView="chat" onNavigate={() => {}} onOpenSettings={() => {}} healthKey={0} />
    );
    await user.click(await screen.findByRole('button', { name: /Vault ativa: Obsidian/ }));
    await user.click(screen.getByRole('menuitemradio', { name: /Culinária/ }));

    await waitFor(() => expect(selectSpy).toHaveBeenCalledWith('culinaria'));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(listSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    window.removeEventListener(CORPUS_CHANGED_EVENT, changed);
  });

  it('vault: criar valida o nome, envia ícone e cor e ativa a vault nova', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const createSpy = vi
      .spyOn(bridge, 'createVault')
      .mockResolvedValue({ ok: true, vault: { ...CULINARIA, id: 'receitas' } });
    const selectSpy = vi.spyOn(bridge, 'selectVault').mockResolvedValue({ ok: true, active: 'receitas' });
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWithVaults(<VaultDialog onClose={onClose} />);
    await user.click(screen.getByRole('button', { name: 'Criar vault' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Dê um nome');
    expect(createSpy).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('Nome'), 'Receitas');
    await user.click(screen.getByRole('button', { name: 'Ícone Código' }));
    await user.click(screen.getByRole('button', { name: 'Cor Rosa' }));
    await user.click(screen.getByRole('button', { name: 'Criar vault' }));

    await waitFor(() => expect(createSpy).toHaveBeenCalledWith('Receitas', 'code', 'rose', []));
    expect(selectSpy).toHaveBeenCalledWith('receitas');
    expect(onClose).toHaveBeenCalled();
  });

  it('vault: seletor mostra as contagens, fecha com Esc e abre pelo chip do campo de pergunta', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const user = userEvent.setup();

    renderWithVaults(
      <Sidebar activeView="chat" onNavigate={() => {}} onOpenSettings={() => {}} healthKey={0} />
    );
    const switcher = await screen.findByRole('button', { name: /Vault ativa: Obsidian/ });
    expect(switcher.textContent).toContain('42 notas · 2 pastas');

    await user.click(switcher);
    const menu = screen.getByRole('menu', { name: 'Vaults' });
    expect(within(menu).getByRole('menuitemradio', { name: /Culinária/ }).textContent).toContain('7 notas · 0 pastas');
    expect(within(menu).getByRole('menuitem', { name: 'Nova vault' })).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Gerenciar vaults' })).toBeTruthy();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu', { name: 'Vaults' })).toBeNull();

    act(() => {
      window.dispatchEvent(new Event(OPEN_VAULT_MENU_EVENT));
    });
    expect(screen.getByRole('menu', { name: 'Vaults' })).toBeTruthy();
  });

  it('vault: aba Vaults mostra a lista e o detalhe com as pastas reais da vault', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const user = userEvent.setup();

    renderWithVaults(<VaultsTab onOpenQueue={() => {}} />);
    const roots = await screen.findByRole('list', { name: 'Pastas de Obsidian' });
    expect(within(roots).getAllByRole('listitem')).toHaveLength(2);
    expect(within(roots).getByText('Area de TI')).toBeTruthy();
    expect(within(roots).getByText('40 notas')).toBeTruthy();
    expect(screen.getByText('Ativa agora')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /Culinária/ }));
    expect(await screen.findByText('Nenhuma pasta indexada nesta vault ainda.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ativar esta vault' })).toBeTruthy();
    expect((screen.getByLabelText('Nome da vault') as HTMLInputElement).value).toBe('Culinária');
  });

  it('vault: renomear salva ao sair do campo; ícone e cor valem na hora', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const updateSpy = vi.spyOn(bridge, 'updateVault').mockResolvedValue({ ok: true });
    const user = userEvent.setup();

    renderWithVaults(<VaultsTab onOpenQueue={() => {}} />);
    const name = await screen.findByLabelText('Nome da vault');
    await user.clear(name);
    await user.type(name, 'Pessoal');
    await user.tab();
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith('obsidian', { name: 'Pessoal' }));

    await user.click(screen.getByRole('button', { name: 'Ícone Código' }));
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith('obsidian', { icon: 'code' }));
    await user.click(screen.getByRole('button', { name: 'Cor Rosa' }));
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith('obsidian', { color: 'rose' }));
  });

  it('vault: excluir só habilita depois de digitar o nome; a única vault não pode ser excluída', async () => {
    const listSpy = vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const deleteSpy = vi.spyOn(bridge, 'deleteVault').mockResolvedValue({ ok: true });
    const user = userEvent.setup();

    renderWithVaults(<VaultsTab onOpenQueue={() => {}} />);
    await user.click(await screen.findByRole('button', { name: /Culinária/ }));
    await user.click(await screen.findByRole('button', { name: 'Excluir…' }));
    const confirmBtn = screen.getByRole('button', { name: 'Excluir vault' }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
    await user.type(screen.getByLabelText('Digite Culinária para confirmar'), 'Culinária');
    expect(confirmBtn.disabled).toBe(false);
    await user.click(confirmBtn);
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith('culinaria', 'Culinária'));

    cleanup();
    listSpy.mockResolvedValue({ active: 'obsidian', vaults: [OBSIDIAN] });
    renderWithVaults(<VaultsTab onOpenQueue={() => {}} />);
    expect(((await screen.findByRole('button', { name: 'Excluir…' })) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('É a única vault: crie outra antes de excluir esta.')).toBeTruthy();
  });

  it('vault: remover pasta pede confirmação, usa a confirmação do backend e avisa o app', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const removeSpy = vi.spyOn(bridge, 'removeCorpusRoot').mockResolvedValue({ ok: true, removed_notes: 2 });
    const changed = vi.fn();
    window.addEventListener(CORPUS_CHANGED_EVENT, changed);
    const user = userEvent.setup();

    renderWithVaults(<VaultsTab onOpenQueue={() => {}} />);
    await user.click(await screen.findByRole('button', { name: 'Remover a pasta Windows do índice' }));
    expect(removeSpy).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Remover do índice' }));

    await waitFor(() => expect(removeSpy).toHaveBeenCalledWith(String.raw`C:\Obsidian\Windows`, 'REMOVER'));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    window.removeEventListener(CORPUS_CHANGED_EVENT, changed);
  });

  it('vault: indexar pasta de outra vault ativa ela e abre a Fila', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const selectSpy = vi.spyOn(bridge, 'selectVault').mockResolvedValue({ ok: true, active: 'culinaria' });
    const onOpenQueue = vi.fn();
    const user = userEvent.setup();

    renderWithVaults(<VaultsTab onOpenQueue={onOpenQueue} />);
    await user.click(await screen.findByRole('button', { name: /Culinária/ }));
    await user.click(screen.getByRole('button', { name: 'Indexar pasta' }));

    await waitFor(() => expect(selectSpy).toHaveBeenCalledWith('culinaria'));
    await waitFor(() => expect(onOpenQueue).toHaveBeenCalled());
  });

  it('vault: tela inicial mostra a vault que vai responder e, vazia, leva à Fila', async () => {
    const onOpenQueue = vi.fn();
    const user = userEvent.setup();

    render(<WelcomeScreen vault={OBSIDIAN} onOpenQueue={onOpenQueue} />);
    expect(screen.getByRole('heading', { name: 'Obsidian' })).toBeTruthy();
    expect(screen.getByText(/42 notas desta vault/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Indexar uma pasta na Fila' })).toBeNull();

    cleanup();
    render(<WelcomeScreen vault={{ ...CULINARIA, note_count: 0 }} onOpenQueue={onOpenQueue} />);
    await user.click(screen.getByRole('button', { name: 'Indexar uma pasta na Fila' }));
    expect(onOpenQueue).toHaveBeenCalled();
  });
});

describe('vaults: monitor de pasta acompanha a vault', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('vault: com o monitor ligado, trocar de vault deixa o toggle desligado', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    vi.spyOn(bridge, 'selectVault').mockResolvedValue({ ok: true, active: 'culinaria' });
    vi.spyOn(bridge, 'startWatcher').mockResolvedValue({ active: true } as never);
    const { result } = renderHook(() => ({ queue: useIndexJob(), vaults: useVaults() }), {
      wrapper: VaultsProvider,
    });

    act(() => result.current.queue.setFolderPath(String.raw`C:\Notas\Obsidian`));
    await act(async () => {
      await result.current.queue.toggleWatcher();
    });
    expect(result.current.queue.watcherActive).toBe(true);

    await act(async () => {
      await result.current.vaults.select('culinaria');
    });
    expect(result.current.queue.watcherActive).toBe(false);
  });
});
