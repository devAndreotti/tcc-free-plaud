import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MessageBubble, { type MessageData } from './MessageBubble';
import type { AskCitation, AskResult } from '../services/bridge';
import { GRAPH_FOCUS_EVENT } from '../lib/vaultGraph';

const cite = (n: number, path: string): AskCitation => ({
  note_id: `nota-${n}`,
  note_version: 1,
  chunk_id: `nota-${n}::v1::ofs-${n}`,
  snippet: `Trecho ${n}`,
  source_path: path,
  char_start: n * 100,
  char_end: n * 100 + 80,
});

const answer = (ask: Partial<AskResult>): MessageData => ({
  id: 'm1',
  role: 'assistant',
  content: ask.answer ?? '',
  timestamp: new Date(),
  ask: {
    query: 'Como funciona?',
    status: 'answer',
    no_answer: false,
    answer: 'Resposta.',
    claims: [],
    citations: [],
    limitations: [],
    reason_for_no_answer: null,
    latency_ms: 842,
    strategy: 'hybrid',
    top_k: 5,
    answer_provider: 'extractive',
    ...ask,
  },
});

describe('MessageBubble com resposta estruturada', () => {
  afterEach(() => cleanup());

  it('numera as fontes pela ordem das afirmações e mostra apoio parcial', () => {
    const a = cite(1, 'Projetos/Arquitetura.md');
    const b = cite(2, 'Projetos/Pipeline.md');
    render(
      <MessageBubble
        message={answer({
          claims: [
            { text: 'Primeira afirmação.', citations: [a], support_level: 'direct' },
            { text: 'Segunda afirmação.', citations: [b], support_level: 'partial' },
          ],
          citations: [a, b],
          limitations: ['Só duas fontes.'],
        })}
      />
    );

    expect(screen.getByRole('button', { name: 'Fonte 1' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fonte 2, apoio parcial' })).toBeTruthy();
    expect(screen.getByText('Arquitetura')).toBeTruthy();
    expect(screen.getByText('Projetos/Pipeline.md')).toBeTruthy();
    expect(screen.getByText('apoio parcial', { selector: '.msg__support' })).toBeTruthy();
    expect(screen.getByText('Só duas fontes.')).toBeTruthy();
    expect(screen.getByText('842 ms')).toBeTruthy();
    expect(screen.getByText('· a partir de 2 notas')).toBeTruthy();
  });

  it('destaca a fonte ao passar o mouse no número da citação', async () => {
    const user = userEvent.setup();
    const a = cite(1, 'Projetos/Arquitetura.md');
    const { container } = render(
      <MessageBubble message={answer({ claims: [{ text: 'Afirmação.', citations: [a], support_level: 'direct' }], citations: [a] })} />
    );

    await user.hover(screen.getByRole('button', { name: 'Fonte 1' }));
    expect(container.querySelector('.msg__source')?.classList.contains('is-hl')).toBe(true);
  });

  it('passar o mouse na fonte avisa o grafo qual nota destacar, e sair solta o destaque', async () => {
    const user = userEvent.setup();
    const focused: (string | null)[] = [];
    const onFocus = (e: Event) => focused.push((e as CustomEvent<string | null>).detail);
    window.addEventListener(GRAPH_FOCUS_EVENT, onFocus);
    const a = cite(1, 'Estudos/Cisco/Cisco.md');
    render(<MessageBubble message={answer({ claims: [{ text: 'Afirmação.', citations: [a], support_level: 'direct' }], citations: [a] })} />);

    await user.hover(screen.getByText('Trecho 1'));
    await user.unhover(screen.getByText('Trecho 1'));
    window.removeEventListener(GRAPH_FOCUS_EVENT, onFocus);

    expect(focused).toEqual(['nota-1', null]);
  });

  it('resposta escrita pela IA aparece no lugar dos trechos, com o modelo no rodapé', () => {
    const a = cite(1, 'Estudos/Infra/Docker.md');
    render(
      <MessageBubble
        message={answer({
          answer: 'Docker compartilha o kernel do host; a VM traz um SO inteiro.',
          generated: true,
          answer_provider: 'ollama',
          answer_model: 'qchat:latest',
          claims: [{ text: 'Docker vs Máquinas Virtuais - [!note]', citations: [a], support_level: 'partial' }],
          citations: [a],
        })}
      />
    );

    expect(screen.getByText('Docker compartilha o kernel do host; a VM traz um SO inteiro.')).toBeTruthy();
    expect(screen.queryByText('Docker vs Máquinas Virtuais - [!note]')).toBeNull();
    expect(screen.getByText('ollama · qchat:latest')).toBeTruthy();
    expect(screen.getByText('Docker')).toBeTruthy(); // a fonte continua listada
  });

  it('explica a falta de resposta e oferece buscar por palavra-chave', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <MessageBubble
        message={answer({
          status: 'no_answer',
          no_answer: true,
          answer: null,
          reason_for_no_answer: 'insufficient_hybrid_specificity',
          limitations: ['Os hits híbridos recuperados não apresentam evidência lexical suficiente.'],
        })}
        onRetry={onRetry}
      />
    );

    expect(screen.getByText('Não encontrei isso no vault.')).toBeTruthy();
    expect(screen.getByText('motivo: insufficient_hybrid_specificity')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Buscar só por palavra-chave' }));
    expect(onRetry).toHaveBeenCalledWith('Como funciona?', 'lexical');
  });

  it('não oferece palavra-chave quando nenhuma busca achou trecho algum', () => {
    render(
      <MessageBubble
        message={answer({ status: 'no_answer', no_answer: true, answer: null, reason_for_no_answer: 'no_retrieval_hits', limitations: [] })}
        onRetry={vi.fn()}
      />
    );

    expect(screen.queryByRole('button', { name: 'Buscar só por palavra-chave' })).toBeNull();
  });

  it('com o corpus vazio, manda indexar em vez de sugerir outra busca', () => {
    render(
      <MessageBubble
        message={answer({ status: 'no_answer', no_answer: true, answer: null, reason_for_no_answer: 'empty_corpus', limitations: [] })}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByText('O corpus ainda está vazio.')).toBeTruthy();
    expect(screen.getByText(/Indexe a pasta do vault na Fila/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Buscar só por palavra-chave' })).toBeNull();
  });

  it('encurta caminhos longos da fonte e usa o note_id quando não há caminho', () => {
    const longa = cite(1, 'C:\\Users\\usuario\\vault\\projetos\\2025\\nota.md');
    const semCaminho = { ...cite(2, ''), source_path: null } as unknown as AskCitation;
    render(
      <MessageBubble
        message={answer({
          claims: [{ text: 'Afirmação com duas fontes.', citations: [longa, semCaminho], support_level: 'direct' }],
          citations: [longa, semCaminho],
        })}
      />
    );

    expect(screen.getByText('…/projetos/2025/nota.md')).toBeTruthy();
    expect(screen.getByTitle('nota-2').textContent).toBe('nota-2');
  });

  it('diz qual termo da pergunta não está no corpus, sem oferecer palavra-chave', () => {
    const limitation = 'A pergunta cita "senha", que não aparece em nenhuma nota do corpus.';
    render(
      <MessageBubble
        message={answer({ status: 'no_answer', no_answer: true, answer: null, reason_for_no_answer: 'query_term_not_in_corpus', limitations: [limitation] })}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByText(limitation)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Buscar só por palavra-chave' })).toBeNull();
  });

  it('clicar no título ou no corpo do card abre a nota no trecho citado', async () => {
    const user = userEvent.setup();
    const onOpenSource = vi.fn();
    const a = cite(1, 'Projetos/Arquitetura.md');
    render(<MessageBubble message={answer({ claims: [{ text: 'Afirmação.', citations: [a], support_level: 'direct' }], citations: [a] })} onOpenSource={onOpenSource} />);

    await user.click(screen.getByRole('button', { name: 'Abrir Arquitetura no trecho citado' }));
    expect(onOpenSource).toHaveBeenLastCalledWith('nota-1', 'nota-1::v1::ofs-1');

    await user.click(screen.getByText('Trecho 1'));
    expect(onOpenSource).toHaveBeenCalledTimes(2);
    expect(onOpenSource).toHaveBeenLastCalledWith('nota-1', 'nota-1::v1::ofs-1');
  });

  it('Enter e Espaço com o card focado abrem a nota no trecho citado', async () => {
    const user = userEvent.setup();
    const onOpenSource = vi.fn();
    const a = cite(1, 'Projetos/Arquitetura.md');
    const { container } = render(
      <MessageBubble message={answer({ claims: [{ text: 'Afirmação.', citations: [a], support_level: 'direct' }], citations: [a] })} onOpenSource={onOpenSource} />
    );

    (container.querySelector('.msg__source') as HTMLElement).focus();
    await user.keyboard('{Enter}');
    expect(onOpenSource).toHaveBeenCalledTimes(1);
    expect(onOpenSource).toHaveBeenLastCalledWith('nota-1', 'nota-1::v1::ofs-1');

    await user.keyboard(' ');
    expect(onOpenSource).toHaveBeenCalledTimes(2);
  });
});
