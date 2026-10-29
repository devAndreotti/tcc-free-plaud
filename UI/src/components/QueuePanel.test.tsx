import { useState, type ReactNode } from 'react';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QueuePanel from './QueuePanel';
import { QueueProvider } from '../contexts/QueueContext';

// QueuePanel agora depende do QueueContext — todo render precisa do Provider.
const Providers = ({ children }: { children: ReactNode }) => (
  <QueueProvider>{children}</QueueProvider>
);
const renderQueuePanel = () => render(<Providers><QueuePanel /></Providers>);

const bridgeMock = vi.hoisted(() => ({
  selectFolder: vi.fn(),
  startIndexJob: vi.fn(),
  getIndexJob: vi.fn(),
  cancelIndexJob: vi.fn(),
  startWatcher: vi.fn(),
  stopWatcher: vi.fn(),
  loadVaultPath: vi.fn(),
  saveVaultPath: vi.fn(),
  scanVault: vi.fn(),
  listCorpusRoots: vi.fn(),
  removeCorpusRoot: vi.fn(),
  listIgnoredPaths: vi.fn().mockResolvedValue([]),
  ignoreIndexPaths: vi.fn(),
  unignoreIndexPaths: vi.fn(),
  retryIndexPaths: vi.fn(),
  openIndexPath: vi.fn(),
}));

vi.mock('../services/bridge', () => ({
  bridge: bridgeMock,
}));

const runningJob = {
  job_id: 'job-queue-1',
  status: 'running',
  source_path: 'C:\\Vault',
  started_at: '2026-05-26T10:00:00+00:00',
  finished_at: null,
  progress: {
    phase: 'embedding',
    current_path: 'C:\\Vault\\nota.md',
    total_found: 3,
    processed_count: 1,
    indexed_count: 1,
    unchanged_count: 0,
    failed_count: 0,
    skipped_count: 0,
    elapsed_ms: 100,
    warmup_ms: 0,
    embedding_ms: 40,
    writing_ms: 0,
    committed_count: 0,
    commit_mode_requested: 'auto',
    commit_mode_resolved: 'microbatch',
    batch_index: 1,
    batch_total: 2,
    message: 'Processando nota.md',
  },
  result: null,
  error_code: null,
  message: null,
  last_errors: [],
  cancel_requested: false,
  files_per_second: 10,
  chunks_per_second: 20,
  eta_seconds: 1,
};

const CORPUS_ROOTS = [
  { root: 'D:\\Notas\\Obsidian', notes_count: 42 },
  { root: 'D:\\Notas\\Culinaria', notes_count: 7 },
];

describe('QueuePanel', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    bridgeMock.selectFolder.mockReset();
    bridgeMock.startIndexJob.mockReset();
    bridgeMock.getIndexJob.mockReset();
    bridgeMock.cancelIndexJob.mockReset();
    bridgeMock.startWatcher.mockReset();
    bridgeMock.stopWatcher.mockReset();
    bridgeMock.loadVaultPath.mockReset();
    bridgeMock.saveVaultPath.mockReset();
    bridgeMock.scanVault.mockReset();
    bridgeMock.loadVaultPath.mockResolvedValue('');
    bridgeMock.saveVaultPath.mockResolvedValue(true);
    bridgeMock.scanVault.mockResolvedValue([]);
    bridgeMock.listCorpusRoots.mockResolvedValue([]);
    bridgeMock.removeCorpusRoot.mockReset();

    bridgeMock.selectFolder.mockResolvedValue('C:\\Vault');
    bridgeMock.startIndexJob.mockResolvedValue(runningJob);
    bridgeMock.getIndexJob.mockResolvedValue(runningJob);
    bridgeMock.cancelIndexJob.mockResolvedValue({ ...runningJob, status: 'cancelled', cancel_requested: true });
    bridgeMock.startWatcher.mockResolvedValue({ ok: true, active: true, directory: 'C:\\Vault' });
    bridgeMock.stopWatcher.mockResolvedValue({ ok: true, active: false, directory: null });
  });

  it('cria job e mostra progresso consultado do backend', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalledWith('C:\\Vault', false);
    });

    expect(await screen.findByText('job-queue-1')).toBeTruthy();
    // Etapa atual marcada, com o lote do embedding.
    expect(screen.getByText('Modelo de busca semântica').closest('li')?.getAttribute('aria-current')).toBe('step');
    expect(screen.getByText('lote 1 de 2')).toBeTruthy();
    expect(screen.getByText('de 3 arquivos')).toBeTruthy();
    expect(screen.getByText('10,0')).toBeTruthy();
    expect(screen.getByText('auto → microbatch')).toBeTruthy();
    expect(screen.getByRole('progressbar', { name: 'Progresso do job' }).getAttribute('aria-valuenow')).toBe('33');
  });

  it('cancela job ativo sem iniciar outro', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));
    await screen.findByText('job-queue-1');
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    await waitFor(() => {
      expect(bridgeMock.cancelIndexJob).toHaveBeenCalledWith('job-queue-1');
    });
  });

  it('mostra as falhas do job com nome do arquivo, motivo e detalhe técnico', async () => {
    const user = userEvent.setup();
    bridgeMock.getIndexJob.mockResolvedValue({
      ...runningJob,
      last_errors: [
        { source_path: 'C:\\Vault\\notes\\rascunho.md', message: 'Encoding inválido.', error_code: 'BAD_ENCODING' },
      ],
    });
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    const failures = await screen.findByRole('region', { name: 'Arquivos com problema' });
    expect(within(failures).getByText('Falha ao indexar')).toBeTruthy();
    expect(within(failures).getByText('rascunho.md')).toBeTruthy();
    expect(within(failures).getByText('Vault › notes')).toBeTruthy();
    expect(within(failures).getByText('Encoding inválido.')).toBeTruthy();
  });

  it('nota vazia vira aviso amigável e "Ignorar todos" tira o grupo da lista', async () => {
    const user = userEvent.setup();
    bridgeMock.ignoreIndexPaths.mockResolvedValue({ ok: true, ignored: 2, removed_notes: 0 });
    bridgeMock.getIndexJob.mockResolvedValue({
      ...runningJob,
      last_errors: [
        { source_path: 'C:\\Vault\\Templates\\Mensal.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' },
        { source_path: 'C:\\Vault\\Templates\\Vídeo.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' },
      ],
    });
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    const failures = await screen.findByRole('region', { name: 'Arquivos com problema' });
    expect(within(failures).getByText(/Notas sem conteúdo/)).toBeTruthy();
    expect(within(failures).queryByText('EMPTY_CONTENT')).toBeNull();
    await user.click(within(failures).getByRole('button', { name: 'Ignorar todos' }));

    expect(bridgeMock.ignoreIndexPaths).toHaveBeenCalledWith(['C:\\Vault\\Templates\\Mensal.md', 'C:\\Vault\\Templates\\Vídeo.md']);
    expect(await within(failures).findByText('Tudo resolvido neste job.')).toBeTruthy();
  });

  it('tentar de novo tira o arquivo da lista quando indexa e mantém quando continua falhando', async () => {
    const user = userEvent.setup();
    bridgeMock.retryIndexPaths
      .mockResolvedValueOnce({ ok: true, results: [{ name: 'a.md', source_path: 'C:\\Vault\\a.md', status: 'failed', chunks: 0, error_code: 'EMPTY_CONTENT', message: 'EMPTY_CONTENT' }] })
      .mockResolvedValueOnce({ ok: true, results: [{ name: 'a.md', source_path: 'C:\\Vault\\a.md', status: 'indexed', chunks: 2, error_code: null, message: null }] });
    bridgeMock.getIndexJob.mockResolvedValue({
      ...runningJob,
      last_errors: [{ source_path: 'C:\\Vault\\a.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' }],
    });
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));

    await user.click(await screen.findByRole('button', { name: 'Tentar indexar a.md de novo' }));
    expect(await screen.findByText('1 arquivo continua com problema.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Tentar indexar a.md de novo' }));
    expect(await screen.findByText('1 arquivo indexado.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Tentar indexar a.md de novo' })).toBeNull();
  });

  it('lista os ignorados e "Voltar a indexar" desfaz', async () => {
    const user = userEvent.setup();
    bridgeMock.listIgnoredPaths
      .mockResolvedValueOnce([{ path: 'C:\\Vault\\Templates\\Mensal.md', reason: 'usuario', ignored_at: '2026-10-18T20:00:00-03:00' }])
      .mockResolvedValue([]);
    bridgeMock.unignoreIndexPaths.mockResolvedValue({ ok: true, restored: 1, queued: 1 });
    renderQueuePanel();

    await user.click(await screen.findByText(/Ignorados na indexação/));
    await user.click(screen.getByRole('button', { name: 'Voltar a indexar Mensal.md' }));

    expect(bridgeMock.unignoreIndexPaths).toHaveBeenCalledWith(['C:\\Vault\\Templates\\Mensal.md']);
    await waitFor(() => expect(screen.queryByText(/Ignorados na indexação/)).toBeNull());
  });

  it('falha de modelo de voz leva direto para Configurações › Voz', async () => {
    const user = userEvent.setup();
    const onOpenSettings = vi.fn();
    bridgeMock.getIndexJob.mockResolvedValue({
      ...runningJob,
      last_errors: [
        { source_path: 'Audio/aula-07.m4a', message: 'Modelo de voz não instalado.', error_code: 'AUDIO_MODEL_NOT_READY' },
      ],
    });
    render(<Providers><QueuePanel onOpenSettings={onOpenSettings} /></Providers>);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('button', { name: 'Indexar' }));
    await user.click(await screen.findByRole('button', { name: 'Abrir Voz' }));

    expect(onOpenSettings).toHaveBeenCalledWith('voz');
  });

  it('liga e desliga o watcher de pasta', async () => {
    const user = userEvent.setup();
    renderQueuePanel();

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await user.click(screen.getByRole('checkbox', { name: 'Monitorar pasta' }));

    await waitFor(() => {
      expect(bridgeMock.startWatcher).toHaveBeenCalledWith('C:\\Vault');
    });
    await waitFor(() => {
      expect((screen.getByRole('checkbox', { name: 'Monitorar pasta' }) as HTMLInputElement).checked).toBe(true);
    });

    await user.click(screen.getByRole('checkbox', { name: 'Monitorar pasta' }));
    await waitFor(() => {
      expect(bridgeMock.stopWatcher).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect((screen.getByRole('checkbox', { name: 'Monitorar pasta' }) as HTMLInputElement).checked).toBe(false);
    });
  });

  it('continua consultando o job mesmo depois de QueuePanel ser desmontado (troca de aba)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ delay: null });

    // Simula a troca de aba do App: QueueProvider fica montado o tempo
    // todo, mas QueuePanel é desmontado/remontado conforme um toggle,
    // exatamente como {workspaceView === 'queue' && <QueuePanel/>} em App.tsx.
    const Harness = () => {
      const [showQueue, setShowQueue] = useState(true);
      return (
        <Providers>
          <button type="button" onClick={() => setShowQueue((prev) => !prev)}>
            alternar aba
          </button>
          {showQueue && <QueuePanel />}
        </Providers>
      );
    };

    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Escolher pasta' }));
    await screen.findByDisplayValue('C:\\Vault');
    await user.click(screen.getByRole('button', { name: 'Indexar' }));
    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalled();
    });

    const callsBeforeLeaving = bridgeMock.getIndexJob.mock.calls.length;

    // Sai da aba (desmonta QueuePanel, mas o QueueProvider continua montado).
    await user.click(screen.getByRole('button', { name: 'alternar aba' }));
    expect(screen.queryByText('job-queue-1')).toBeNull();

    // Avança o tempo do polling (1s) sem QueuePanel montado.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(bridgeMock.getIndexJob.mock.calls.length).toBeGreaterThan(callsBeforeLeaving);

    // Volta para a aba: o job continua lá, sem precisar recriar nada.
    await user.click(screen.getByRole('button', { name: 'alternar aba' }));
    expect(await screen.findByText('job-queue-1')).toBeTruthy();

    vi.useRealTimers();
  });

  it('regressao: lista as pastas indexadas no corpus com a contagem de notas', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    renderQueuePanel();

    expect(await screen.findByText('Obsidian')).toBeTruthy();
    expect(screen.getByText('42 notas')).toBeTruthy();
    expect(screen.getByText('Culinaria')).toBeTruthy();
    expect(screen.getByText('7 notas')).toBeTruthy();
    expect(screen.getByTitle('D:\\Notas\\Culinaria')).toBeTruthy();
  });

  it('regressao: Reindexar usa a raiz da linha e chama startIndexJob com ela', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Reindexar' }));

    await waitFor(() => {
      expect(bridgeMock.startIndexJob).toHaveBeenCalledWith('D:\\Notas\\Culinaria', false);
    });
  });

  it('regressao: Remover do corpus só chama removeCorpusRoot depois de digitar REMOVER e recarrega a lista', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValueOnce(CORPUS_ROOTS).mockResolvedValue([CORPUS_ROOTS[0]]);
    bridgeMock.removeCorpusRoot.mockResolvedValue({ ok: true, removed_notes: 7 });
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    expect((within(row).getByRole('button', { name: 'Remover do corpus' }) as HTMLButtonElement).disabled).toBe(true);
    expect(bridgeMock.removeCorpusRoot).not.toHaveBeenCalled();

    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    await waitFor(() => {
      expect(bridgeMock.removeCorpusRoot).toHaveBeenCalledWith('D:\\Notas\\Culinaria', 'REMOVER');
    });
    await waitFor(() => {
      expect(screen.queryByText('Culinaria')).toBeNull();
    });
    expect(bridgeMock.listCorpusRoots).toHaveBeenCalledTimes(2);
  });

  it('regressao: Remover do corpus mostra Removendo… e desabilita o painel enquanto a remoção roda', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    bridgeMock.removeCorpusRoot.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    const pending = await within(row).findByRole('button', { name: 'Removendo…' });
    expect((pending as HTMLButtonElement).disabled).toBe(true);
    expect((within(row).getByLabelText('Digite REMOVER para confirmar') as HTMLInputElement).disabled).toBe(true);
    expect((within(row).getByRole('button', { name: 'Cancelar' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('regressao: Remover do corpus mostra N notas removidas, avisa a sidebar e recarrega a lista', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValueOnce(CORPUS_ROOTS).mockResolvedValue([CORPUS_ROOTS[0]]);
    bridgeMock.removeCorpusRoot.mockResolvedValue({ ok: true, removed_notes: 7 });
    const onCorpusChanged = vi.fn();
    window.addEventListener('escolio:corpus-changed', onCorpusChanged);
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    expect(await screen.findByText('Culinaria saiu do corpus: 7 notas removidas.')).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText('Culinaria')).toBeNull();
    });
    expect(bridgeMock.listCorpusRoots).toHaveBeenCalledTimes(2);
    expect(onCorpusChanged).toHaveBeenCalled();
    window.removeEventListener('escolio:corpus-changed', onCorpusChanged);
  });

  it('regressao: Remover do corpus sai de Removendo… e mostra o erro quando o bridge rejeita', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    bridgeMock.removeCorpusRoot.mockRejectedValue(new Error('Backend indisponível'));
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    await user.type(within(row).getByLabelText('Digite REMOVER para confirmar'), 'REMOVER');
    await user.click(within(row).getByRole('button', { name: 'Remover do corpus' }));

    expect(await screen.findByText('Backend indisponível')).toBeTruthy();
    expect(within(row).queryByRole('button', { name: 'Removendo…' })).toBeNull();
    expect((within(row).getByRole('button', { name: 'Remover do corpus' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('regressao: o campo de confirmação de Remover ganha foco e Esc cancela sem remover', async () => {
    bridgeMock.listCorpusRoots.mockResolvedValue(CORPUS_ROOTS);
    const user = userEvent.setup();
    renderQueuePanel();

    const row = (await screen.findByText('Culinaria')).closest('li') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: 'Remover' }));
    expect(document.activeElement).toBe(within(row).getByLabelText('Digite REMOVER para confirmar'));

    await user.keyboard('{Escape}');
    expect(within(row).queryByRole('alertdialog')).toBeNull();
    expect(bridgeMock.removeCorpusRoot).not.toHaveBeenCalled();
  });
});
