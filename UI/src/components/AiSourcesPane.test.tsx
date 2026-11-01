import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { bridge } from '../services/bridge';
import { AiSourcesPane } from './AiSourcesPane';

const renderPane = (props: Partial<Parameters<typeof AiSourcesPane>[0]> = {}) => {
  const onUse = vi.fn();
  const onKeySaved = vi.fn();
  render(
    <AiSourcesPane provider="ollama" baseUrl="" keysConfigured={{}} onUse={onUse} onKeySaved={onKeySaved} {...props} />,
  );
  return { onUse, onKeySaved };
};

describe('AiSourcesPane', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('mostra os provedores com logo e marca o que está em uso', () => {
    renderPane();

    for (const name of ['Ollama', 'LM Studio', 'OpenAI', 'OpenRouter', 'Groq', 'Google Gemini']) {
      expect(screen.getByRole('img', { name: `Logo ${name}` })).toBeTruthy();
    }
    expect(screen.getAllByText('Em uso')).toHaveLength(1);
    expect(screen.getByText('no computador')).toBeTruthy();
  });

  it('usar um provedor local troca o rascunho sem URL', async () => {
    const user = userEvent.setup();
    const { onUse } = renderPane();

    await user.click(screen.getAllByRole('button', { name: 'Usar na resposta' })[1]);

    expect(onUse).toHaveBeenCalledWith({ answer_provider: 'lmstudio', answer_base_url: '' });
  });

  it('a chave é salva para o provedor do cartão', async () => {
    const user = userEvent.setup();
    const save = vi.spyOn(bridge, 'saveApiKey').mockResolvedValue({ ok: true, configured: true, local_env_path: '.env' });
    const { onKeySaved } = renderPane();

    await user.click(screen.getAllByRole('button', { name: 'Conectar' })[1]);
    await user.type(screen.getByLabelText('Chave de API'), 'sk-or-123');
    await user.click(screen.getByRole('button', { name: 'Salvar chave' }));

    expect(save).toHaveBeenCalledWith('sk-or-123', 'openrouter');
    expect(onKeySaved).toHaveBeenCalled();
  });

  it('com chave salva, testa, escolhe o modelo e só usa depois do aviso de privacidade', async () => {
    const user = userEvent.setup();
    vi.spyOn(bridge, 'listAnswerModels').mockResolvedValue({
      provider: 'openai-compatible',
      base_url: 'https://api.groq.com/openai/v1',
      status: 'ok',
      models: [{ id: 'modelo-a', label: 'modelo-a', provider: 'openai-compatible', details: {} }],
      latency_ms: 120,
      cached: false,
      message: null,
    });
    const { onUse } = renderPane({ keysConfigured: { groq: true } });

    await user.click(screen.getByRole('button', { name: 'Gerenciar' }));
    await user.click(screen.getByRole('button', { name: 'Testar e listar modelos' }));
    expect(await screen.findByText('Conectado: 1 modelos de conversa.')).toBeTruthy();

    const card = within(screen.getByText('Groq').closest('article') as HTMLElement);
    const use = card.getByRole('button', { name: 'Usar na resposta' }) as HTMLButtonElement;
    expect(use.disabled).toBe(true);
    await user.click(screen.getByRole('checkbox'));
    await user.click(use);

    expect(onUse).toHaveBeenCalledWith({
      answer_provider: 'openai-compatible',
      answer_base_url: 'https://api.groq.com/openai/v1',
      answer_model: 'modelo-a',
    });
  });

  it('provedor de nuvem em uso aparece como nuvem no resumo', () => {
    renderPane({ provider: 'openai-compatible', baseUrl: 'https://openrouter.ai/api/v1/' });

    expect(screen.getByText('OpenRouter', { selector: 'p strong' })).toBeTruthy();
    expect(screen.getByText('na nuvem: pergunta e trechos saem do computador')).toBeTruthy();
  });
});
