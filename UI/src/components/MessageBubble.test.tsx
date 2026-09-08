import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MessageBubble, { TypingIndicator, MessageData } from './MessageBubble';

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
});
