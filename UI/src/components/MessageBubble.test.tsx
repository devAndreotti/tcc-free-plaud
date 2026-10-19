import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import MessageBubble, { TypingIndicator } from './MessageBubble';
import type { MessageData } from './MessageBubble';

describe('MessageBubble', () => {
  it('renderiza mensagem do usuario com icone de usuario', () => {
    const message: MessageData = {
      id: 'msg-1',
      role: 'user',
      content: 'Minha pergunta de teste',
      timestamp: new Date(),
    };

    render(<MessageBubble message={message} />);
    expect(screen.getByText('Minha pergunta de teste')).toBeTruthy();
  });

  it('renderiza mensagem da IA com formatacao de titulos e listas', () => {
    const message: MessageData = {
      id: 'msg-2',
      role: 'assistant',
      content: '# Titulo Principal\n## Subtitulo\n### Secao\n- Item 1\n* Item 2\n\nTexto corrido',
      timestamp: new Date(),
    };

    render(<MessageBubble message={message} />);
    expect(screen.getByText('Titulo Principal')).toBeTruthy();
    expect(screen.getByText('Subtitulo')).toBeTruthy();
    expect(screen.getByText('Secao')).toBeTruthy();
    expect(screen.getByText('Item 1')).toBeTruthy();
    expect(screen.getByText('Item 2')).toBeTruthy();
    expect(screen.getByText('Texto corrido')).toBeTruthy();
  });

  it('renderiza typing indicator corretamente', () => {
    render(<TypingIndicator />);
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('indicador de digitação: buscando no vault sem estágio ou durante a busca', () => {
    // Escopado ao container: sem cleanup automático, o indicador do teste anterior continua no DOM.
    const { container } = render(<TypingIndicator stage="retrieving" />);
    expect(within(container).getByRole('status', { name: 'Buscando no vault' })).toBeTruthy();
    expect(within(container).getByText('Buscando no vault…')).toBeTruthy();
  });

  it('indicador de digitação: escrevendo mostra modelo, texto parcial e cursor no fim do texto', () => {
    const { container } = render(<TypingIndicator stage="writing" partial={'Docker roda\nem containers'} model="qwen2.5:3b" />);
    expect(screen.getByText('Escrevendo com qwen2.5:3b…')).toBeTruthy();
    expect(screen.getByText('Docker roda')).toBeTruthy();
    expect(screen.getByText('em containers').querySelector('.msg__cursor')).toBeTruthy();
    expect(container.querySelectorAll('.msg__cursor')).toHaveLength(1);
  });

  it('indicador de digitação: sem modelo, diz que está escrevendo a resposta', () => {
    render(<TypingIndicator stage="writing" />);
    expect(screen.getByText('Escrevendo a resposta…')).toBeTruthy();
  });
});
