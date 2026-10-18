import { act, cleanup, render, renderHook, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { VaultsProvider, CORPUS_CHANGED_EVENT } from '../contexts/VaultsContext';
import { useIndexJob } from '../hooks/useIndexJob';
import { useVaults } from '../hooks/useVaults';
import { bridge, type Vault, type VaultList } from '../services/bridge';
import Sidebar from './Sidebar';
import VaultDialog from './VaultDialog';
import VaultsTab from './VaultsTab';

vi.mock('../hooks/useQueueContext', () => ({
  useQueueContext: () => ({ job: null, watcherActive: false, folderPath: '' }),
}));
vi.mock('../hooks/useCorpusHealth', () => ({ useCorpusHealth: () => null }));

const base = { embedding_model: 'chroma-default', created_at: '2026-10-18T12:00:00-03:00', sqlite_path: null, vector_store_dir: null };
const OBSIDIAN: Vault = { ...base, id: 'obsidian', name: 'Obsidian', icon: 'notes', color: 'violet', folders: [String.raw`C:\Obsidian`], note_count: 42 };
const CULINARIA: Vault = { ...base, id: 'culinaria', name: 'Culinária', icon: 'code', color: 'rose', folders: [], note_count: 7 };
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

  it('vault: aba Vaults renomeia e só habilita excluir depois de digitar o nome', async () => {
    vi.spyOn(bridge, 'listVaults').mockResolvedValue(LIST);
    const updateSpy = vi.spyOn(bridge, 'updateVault').mockResolvedValue({ ok: true });
    const deleteSpy = vi.spyOn(bridge, 'deleteVault').mockResolvedValue({ ok: true });
    const user = userEvent.setup();

    renderWithVaults(<VaultsTab onOpenQueue={() => {}} />);
    await user.click((await screen.findAllByRole('button', { name: 'Renomear' }))[0]);
    const rename = screen.getByLabelText('Novo nome de Obsidian');
    await user.clear(rename);
    await user.type(rename, 'Pessoal');
    await user.click(screen.getByRole('button', { name: 'Salvar nome' }));
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith('obsidian', { name: 'Pessoal' }));

    await user.click(screen.getAllByRole('button', { name: 'Excluir' })[1]);
    const confirmBtn = screen.getByRole('button', { name: 'Excluir índice' });
    expect((confirmBtn as HTMLButtonElement).disabled).toBe(true);
    await user.type(screen.getByLabelText('Digite Culinária para excluir'), 'Culinária');
    expect((confirmBtn as HTMLButtonElement).disabled).toBe(false);
    await user.click(confirmBtn);
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith('culinaria', 'Culinária'));
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
