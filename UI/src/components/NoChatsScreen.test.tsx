import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Vault } from '../services/bridge';
import NoChatsScreen from './NoChatsScreen';

afterEach(cleanup);

const vault = (id: string, name: string, note_count: number) =>
  ({ id, name, note_count, icon: 'notes', color: 'teal', folders: [] }) as unknown as Vault;

const montar = (vaults: Vault[], recent = [] as { id: string; label: string; vaultName: string | null }[]) => {
  const handlers = { onNewChat: vi.fn(), onReopen: vi.fn(), onOpenQueue: vi.fn() };
  render(<NoChatsScreen vaults={vaults} recent={recent} {...handlers} />);
  return handlers;
};

describe('NoChatsScreen', () => {
  it('abre a conversa na vault escolhida', async () => {
    const user = userEvent.setup();
    const h = montar([vault('a', 'Demo', 10), vault('b', 'Obsidian', 632)]);
    expect(screen.getByRole('heading', { name: 'Você fechou todos os chats' })).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Obsidian/ }));
    expect(h.onNewChat).toHaveBeenCalledWith('b');
  });

  it('vault vazia leva à Fila, e o texto muda quando todas estão vazias', async () => {
    const user = userEvent.setup();
    const h = montar([vault('a', 'Nova', 0)]);
    expect(screen.getByText(/ainda está vazia/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Nova/ }));
    expect(h.onOpenQueue).toHaveBeenCalled();
    expect(h.onNewChat).not.toHaveBeenCalled();
  });

  it('reabre uma conversa recente; sem recentes, a seção some', async () => {
    const user = userEvent.setup();
    const h = montar([vault('a', 'Demo', 1)], [{ id: 't1', label: 'método star', vaultName: 'Demo' }]);
    await user.click(screen.getByRole('button', { name: /método star/ }));
    expect(h.onReopen).toHaveBeenCalledWith('t1');
    cleanup();
    montar([vault('a', 'Demo', 1)]);
    expect(screen.queryByRole('region', { name: 'Conversas recentes' })).toBeNull();
  });

  it('com muitas vaults aparece a busca, e ela filtra', async () => {
    const user = userEvent.setup();
    montar(['Um', 'Dois', 'Três', 'Quatro', 'Cinco', 'Seis', 'Sete'].map((n, i) => vault(String(i), n, 1)));
    await user.type(screen.getByLabelText('Buscar vault'), 'sei');
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    await user.clear(screen.getByLabelText('Buscar vault'));
    await user.type(screen.getByLabelText('Buscar vault'), 'zzz');
    expect(screen.getByRole('status').textContent).toContain('Nenhuma vault');
  });

  it('com poucas vaults, sem busca', () => {
    montar([vault('a', 'Demo', 1)]);
    expect(screen.queryByLabelText('Buscar vault')).toBeNull();
  });
});
