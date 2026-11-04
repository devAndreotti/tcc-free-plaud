import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { MessageData } from '../components/MessageBubble';
import { buildPromptHistory, usePromptHistory } from './usePromptHistory';

const user = (content: string) => ({ id: content, role: 'user', content }) as unknown as MessageData;
const ai = (content: string) => ({ id: content, role: 'assistant', content }) as unknown as MessageData;

describe('buildPromptHistory', () => {
  it('vem da aba ativa primeiro, do mais recente para o mais antigo, sem repetir', () => {
    const history = buildPromptHistory(['a', 'b', 'c'], 'b', {
      a: [user('antiga a')],
      b: [user('b1'), ai('resposta'), user('b2'), user('b1')],
      c: [user('c1'), user('b2')],
    });
    expect(history).toEqual(['b1', 'b2', 'c1', 'antiga a']);
  });

  it('sem aba ativa ou sem mensagens, a lista fica vazia', () => {
    expect(buildPromptHistory([], null, {})).toEqual([]);
    expect(buildPromptHistory(['a'], 'a', { a: [ai('só resposta')] })).toEqual([]);
  });
});

const Campo = ({ inicial = '', history }: { inicial?: string; history: string[] }) => {
  const [value, setValue] = useState(inicial);
  const browse = usePromptHistory(history, setValue);
  return (
    <textarea
      aria-label="campo"
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={(event) => { browse(event); }}
    />
  );
};

const campo = () => screen.getByLabelText<HTMLTextAreaElement>('campo');
const seta = (key: 'ArrowUp' | 'ArrowDown', extra = {}) => fireEvent.keyDown(campo(), { key, ...extra });

describe('usePromptHistory', () => {
  it('↑ sobe nos prompts e ↓ volta até ficar vazio', () => {
    render(<Campo history={['novo', 'velho']} />);
    seta('ArrowUp');
    expect(campo().value).toBe('novo');
    seta('ArrowUp');
    expect(campo().value).toBe('velho');
    seta('ArrowUp'); // já no mais antigo: fica nele
    expect(campo().value).toBe('velho');
    seta('ArrowDown');
    expect(campo().value).toBe('novo');
    seta('ArrowDown');
    expect(campo().value).toBe('');
    seta('ArrowDown'); // fora da navegação, a seta não faz nada
    expect(campo().value).toBe('');
  });

  it('↓ devolve o que você estava escrevendo', () => {
    render(<Campo inicial="rascunho" history={['novo']} />);
    campo().setSelectionRange(0, 0);
    seta('ArrowUp');
    expect(campo().value).toBe('novo');
    seta('ArrowDown');
    expect(campo().value).toBe('rascunho');
  });

  it('com o cursor abaixo da primeira linha, ↑ continua movendo o cursor', () => {
    render(<Campo inicial={'linha 1\nlinha 2'} history={['novo']} />);
    campo().setSelectionRange(12, 12);
    seta('ArrowUp');
    expect(campo().value).toBe('linha 1\nlinha 2');
  });

  it('editar um prompt puxado encerra a navegação: ↓ não apaga a edição', () => {
    render(<Campo history={['novo']} />);
    seta('ArrowUp');
    fireEvent.change(campo(), { target: { value: 'novo editado' } });
    seta('ArrowDown');
    expect(campo().value).toBe('novo editado');
  });

  it('não reage com Shift nem durante a composição de um acento', () => {
    render(<Campo history={['novo']} />);
    seta('ArrowUp', { shiftKey: true });
    expect(campo().value).toBe('');
    seta('ArrowUp', { isComposing: true });
    expect(campo().value).toBe('');
  });

  it('sem histórico, a seta fica com o navegador', () => {
    render(<Campo history={[]} />);
    expect(seta('ArrowUp')).toBe(true); // fireEvent devolve true quando nada chamou preventDefault
    expect(campo().value).toBe('');
  });
});
