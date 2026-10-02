import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MessageBubble, { type MessageData } from './MessageBubble';
import type { AskCitation, AskResult } from '../services/bridge';

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

  it('explica a falta de resposta e oferece buscar por palavra-chave', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <MessageBubble
        message={answer({
          status: 'no_answer',
          no_answer: true,
          answer: null,
          reason_for_no_answer: 'no_retrieval_hits',
          limitations: ['Nenhum chunk recuperado contém termos informativos suficientes da pergunta.'],
        })}
        onRetry={onRetry}
      />
    );

    expect(screen.getByText('Não encontrei isso no vault.')).toBeTruthy();
    expect(screen.getByText('motivo: no_retrieval_hits')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Buscar só por palavra-chave' }));
    expect(onRetry).toHaveBeenCalledWith('Como funciona?', 'lexical');
  });
});
