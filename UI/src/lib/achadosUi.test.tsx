import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_APPEARANCE, readAppearance } from '../appearance';
import ExportMenu from '../components/ExportMenu';
import MessageBubble, { type MessageData } from '../components/MessageBubble';
import { bridge, type DoctorReport } from '../services/bridge';
import {
  buildConversationExport,
  conversationFileName,
  printConversation,
  type ConversationExportInput,
} from './conversationExport';
import { lastDoctorReport, refreshDoctor, resetDoctorReport } from './doctorReport';

afterEach(cleanup);

// O Vitest esvazia o CSS importado: o arquivo é lido do disco.
const css = readFileSync(resolve(process.cwd(), 'src/appearance.css'), 'utf-8');

describe('cores de destaque', () => {
  const ACCENTS = ['indigo', 'blue', 'cyan', 'teal', 'green', 'lime', 'amber', 'orange', 'red', 'rose', 'fuchsia'];

  const luminance = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => {
      const channel = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
      return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a: string, b: string) => {
    const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (high + 0.05) / (low + 0.05);
  };
  const tokens = (theme: string, accent: string) => {
    const match = css.match(new RegExp(`:root\\[data-theme="${theme}"\\]\\[data-accent="${accent}"\\]\\s*\\{([^}]*)\\}`));
    expect(match, `${theme}/${accent} sem regra`).toBeTruthy();
    return Object.fromEntries([...match![1].matchAll(/(--[\w-]+):\s*(#[0-9a-f]{6})/g)].map((m) => [m[1], m[2]]));
  };

  it.each(ACCENTS)('%s tem contraste de 4,5:1 nos dois temas', (accent) => {
    const dark = tokens('dark', accent);
    expect(contrast(dark['--accent-blue'], '#ffffff')).toBeGreaterThanOrEqual(4.5);
    expect(contrast(dark['--accent-blue-hover'], '#ffffff')).toBeGreaterThanOrEqual(4.5);
    expect(contrast(dark['--accent-blue-light'], '#17171c')).toBeGreaterThanOrEqual(4.5);
    const light = tokens('light', accent);
    expect(contrast(light['--accent-blue'], '#ffffff')).toBeGreaterThanOrEqual(4.5);
    expect(contrast(light['--accent-blue-hover'], '#ffffff')).toBeGreaterThanOrEqual(4.5);
  });

  it('uma cor nova gravada é lida de volta', () => {
    window.localStorage.setItem('escolio:appearance', JSON.stringify({ accent: 'fuchsia' }));
    expect(readAppearance()).toEqual({ ...DEFAULT_APPEARANCE, accent: 'fuchsia' });
    window.localStorage.removeItem('escolio:appearance');
  });
});

describe('doctorReport', () => {
  const report = { status: 'ok', error_count: 0, warning_count: 1 } as unknown as DoctorReport;
  beforeEach(() => resetDoctorReport());
  afterEach(() => vi.restoreAllMocks());

  it('quem pede durante uma execução recebe a mesma execução, e o resultado fica guardado', async () => {
    const getDoctor = vi.spyOn(bridge, 'getDoctor').mockResolvedValue(report);
    const [a, b] = await Promise.all([refreshDoctor(), refreshDoctor()]);
    expect(getDoctor).toHaveBeenCalledTimes(1);
    expect(a).toBe(report);
    expect(b).toBe(report);
    expect(lastDoctorReport()).toBe(report);
    await refreshDoctor();
    expect(getDoctor).toHaveBeenCalledTimes(2);
  });

  it('depois de uma falha, a próxima chamada roda de novo', async () => {
    vi.spyOn(bridge, 'getDoctor').mockRejectedValueOnce(new Error('caiu')).mockResolvedValueOnce(report);
    await expect(refreshDoctor()).rejects.toThrow('caiu');
    await expect(refreshDoctor()).resolves.toBe(report);
  });
});

const citation = {
  chunk_id: 'c1',
  note_id: 'n1',
  source_path: 'pasta/nota.md',
  char_start: 1,
  char_end: 9,
};
const MENSAGENS = [
  { id: '1', role: 'user', content: 'Pergunta <b>perigosa</b>?' },
  {
    id: '2',
    role: 'assistant',
    content: 'x',
    ask: { answer: 'Resposta <script>alert(1)</script>.', claims: [], citations: [citation] },
  },
] as unknown as MessageData[];
const ENTRADA: ConversationExportInput = {
  title: 'Minha <conversa>',
  messages: MENSAGENS,
  exportedAt: new Date('2026-11-04T12:00:00Z'),
};

describe('exportar conversa', () => {
  it('HTML escapa tudo que vem da conversa', () => {
    const html = buildConversationExport('html', ENTRADA);
    expect(html).toContain('<!doctype html>');
    expect(html).toContain('Pergunta &lt;b&gt;perigosa&lt;/b&gt;?');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).toContain('<title>Minha &lt;conversa&gt;</title>');
    expect(html).not.toContain('<script>');
    expect(html).toContain('pasta/nota.md');
  });

  it('JSON traz as mensagens e as fontes', () => {
    const data = JSON.parse(buildConversationExport('json', ENTRADA));
    expect(data.title).toBe('Minha <conversa>');
    expect(data.messages[0]).toEqual({ role: 'user', text: 'Pergunta <b>perigosa</b>?' });
    expect(data.messages[1].sources[0]).toEqual({ note_id: 'n1', path: 'pasta/nota.md', char_start: 1, char_end: 9 });
  });

  it('texto simples e Markdown respeitam a opção de fontes', () => {
    for (const format of ['txt', 'md', 'html'] as const) {
      expect(buildConversationExport(format, ENTRADA)).toContain('pasta/nota.md');
      expect(buildConversationExport(format, { ...ENTRADA, includeSources: false })).not.toContain('pasta/nota.md');
    }
    expect(JSON.parse(buildConversationExport('json', { ...ENTRADA, includeSources: false })).messages[1].sources).toBeUndefined();
    expect(buildConversationExport('txt', ENTRADA)).toContain('Pergunta:\nPergunta <b>perigosa</b>?');
  });

  it('o nome do arquivo acompanha o formato', () => {
    expect(conversationFileName('Redes: aula 1', 'json')).toBe('Redes- aula 1.json');
    expect(conversationFileName('Redes')).toBe('Redes.md');
  });

  it('PDF imprime só a conversa e limpa depois', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    printConversation(ENTRADA);
    expect(print).toHaveBeenCalledTimes(1);
    const root = document.querySelector('.print-root');
    expect(root?.querySelector('script')).toBeNull();
    expect(root?.textContent).toContain('<script>alert(1)</script>');
    expect(document.documentElement.classList.contains('is-printing')).toBe(true);
    window.dispatchEvent(new Event('afterprint'));
    expect(document.querySelector('.print-root')).toBeNull();
    expect(document.documentElement.classList.contains('is-printing')).toBe(false);
    print.mockRestore();
  });

  it('o menu escolhe o formato e lembra a opção de fontes', async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem('escolio:export:sources');
    const onExport = vi.fn();
    const { unmount } = render(<ExportMenu onExport={onExport} />);
    await user.click(screen.getByRole('button', { name: 'Exportar conversa' }));
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /JSON/ }));
    expect(onExport).toHaveBeenCalledWith('json', false);
    expect(screen.queryByRole('checkbox')).toBeNull();
    unmount();

    render(<ExportMenu onExport={onExport} />);
    await user.click(screen.getByRole('button', { name: 'Exportar conversa' }));
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('checkbox')).toBeNull();
    window.localStorage.removeItem('escolio:export:sources');
  });
});

describe('copiar o prompt', () => {
  it('copia exatamente o que você perguntou', async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    render(<MessageBubble message={{ id: '1', role: 'user', content: 'Qual é a sigla?' } as MessageData} />);
    await user.click(screen.getByRole('button', { name: 'Copiar pergunta' }));
    expect(writeText).toHaveBeenCalledWith('Qual é a sigla?');
    expect(await screen.findByText('Copiado')).toBeTruthy();
    writeText.mockRestore();
  });
});
