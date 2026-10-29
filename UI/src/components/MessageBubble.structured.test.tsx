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
    const { container } = render(
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
    expect(screen.getByText('Escrita pela IA · qchat:latest')).toBeTruthy();
    expect(screen.queryByText(/ollama/)).toBeNull();
    expect(screen.getByText('Docker')).toBeTruthy(); // a fonte continua listada
    expect(container.querySelector('.msg__support')).toBeNull();
  });

  it('explica a falta de resposta e oferece buscar por palavra-chave', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const { container } = render(
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
    expect(container.querySelector('details')?.textContent).toContain('motivo: insufficient_hybrid_specificity');
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

  it('marcadores [n] do texto gerado viram os botões da fonte certa, pelo answer_sources', async () => {
    const user = userEvent.setup();
    const a = cite(1, 'Projetos/Arquitetura.md');
    const b = cite(2, 'Projetos/Pipeline.md');
    const { container } = render(
      <MessageBubble
        message={answer({ answer: 'Primeira frase. [1] Segunda frase. [2]', generated: true, answer_sources: [b.chunk_id, a.chunk_id], citations: [a, b] })}
      />
    );

    // [1] é o contexto do chunk b, que a lista mostra como fonte 2 (e [2] é a fonte 1).
    expect(container.querySelector('.msg__answer')?.textContent).toBe('Primeira frase.2 Segunda frase.1');
    await user.hover(screen.getByRole('button', { name: 'Fonte 2' }));
    const cards = container.querySelectorAll('.msg__source');
    expect(cards[1].classList.contains('is-hl')).toBe(true);
    expect(cards[0].classList.contains('is-hl')).toBe(false);
  });

  it('marcador sem fonte some do texto gerado', () => {
    const a = cite(1, 'Projetos/Arquitetura.md');
    const { container } = render(
      <MessageBubble message={answer({ answer: 'Primeira frase. [1] Frase sem fonte. [5]', generated: true, answer_sources: [a.chunk_id], citations: [a] })} />
    );

    expect(container.querySelector('.msg__answer')?.textContent).toBe('Primeira frase.1 Frase sem fonte.');
    expect(screen.queryByRole('button', { name: 'Fonte 5' })).toBeNull();
  });

  it('sem answer_sources, o texto gerado aparece como veio, com os [n]', () => {
    const a = cite(1, 'Projetos/Arquitetura.md');
    const { container } = render(<MessageBubble message={answer({ answer: 'Primeira frase. [1]', generated: true, citations: [a] })} />);

    expect(container.querySelector('.msg__answer')?.textContent).toBe('Primeira frase. [1]');
  });

  it('Copiar mantém os [n] com a numeração das fontes', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const a = cite(1, 'Projetos/Arquitetura.md');
    const b = cite(2, 'Projetos/Pipeline.md');
    render(
      <MessageBubble
        message={answer({ answer: 'Primeira frase. [1] Segunda frase. [2]', generated: true, answer_sources: [b.chunk_id, a.chunk_id], citations: [a, b] })}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Copiar resposta com as fontes' }));

    expect(writeText).toHaveBeenCalledWith(
      'Primeira frase. [2] Segunda frase. [1]\n\nFontes:\n[1] Projetos/Arquitetura.md (100–180)\n[2] Projetos/Pipeline.md (200–280)'
    );
  });
});

describe('MessageBubble - rodapé da resposta', () => {
  afterEach(() => cleanup());

  it('resposta só com trechos mostra o selo neutro, sem detalhes técnicos', () => {
    const { container } = render(<MessageBubble message={answer({ answer_provider: 'extractive' })} />);

    expect(screen.getByText('Só trechos · sem IA')).toBeTruthy();
    expect(container.querySelector('details')).toBeNull();
  });

  it('IA descartada: motivo em português, código e limitações do modelo nos detalhes; a limitação de busca fica na caixa', () => {
    const a = cite(1, 'Projetos/Arquitetura.md');
    const { container } = render(
      <MessageBubble
        message={answer({
          answer_provider: 'ollama',
          answer_model: 'qchat:latest',
          generated: false,
          answer_discard_reason: 'unsupported_anchor',
          claims: [{ text: 'Afirmação dos trechos.', citations: [a], support_level: 'direct' }],
          citations: [a],
          limitations: [
            'A resposta se apoia em um único trecho recuperado.',
            'Resposta generativa ignorada por nome citado sem suporte: NAO_ENCONTRADO.',
          ],
        })}
      />
    );

    expect(screen.getByText('IA descartada · mostramos o trecho')).toBeTruthy();
    expect(screen.getByText('A IA citou algo que não está nos trechos')).toBeTruthy();
    expect(screen.getByText('Afirmação dos trechos.')).toBeTruthy();
    expect(screen.getByText('Detalhes técnicos')).toBeTruthy();
    const details = container.querySelector('details')?.textContent ?? '';
    expect(details).toContain('unsupported_anchor');
    expect(details).toContain('Resposta generativa ignorada por nome citado sem suporte');
    const limits = container.querySelector('.msg__limits')?.textContent ?? '';
    expect(limits).toContain('A resposta se apoia em um único trecho recuperado.');
    expect(limits).not.toContain('Resposta generativa ignorada');
    expect(screen.queryByText(/ollama/)).toBeNull();
  });

  it('motivo que o app não conhece cai na frase genérica', () => {
    render(<MessageBubble message={answer({ answer_provider: 'ollama', generated: false, answer_discard_reason: 'motivo_novo' })} />);

    expect(screen.getByText('A IA não respondeu com texto a partir dos trechos.')).toBeTruthy();
  });

  it('IA descartada por falta de [n] no texto: diz isso em português', () => {
    render(<MessageBubble message={answer({ answer_provider: 'ollama', generated: false, answer_discard_reason: 'no_source_marker' })} />);

    expect(screen.getByText('A IA escreveu sem citar nenhum trecho')).toBeTruthy();
  });
});
