import { useState } from 'react';
import { bridge, type ModelDiscoveryResult } from '../services/bridge';
import { ProviderLogo } from './ProviderLogos';

// Mesmas URLs de pipeline/src/escolio/providers/cloud_presets.py: a chave do preset vale quando a URL é a dele.
const CLOUD = [
  { id: 'openai', name: 'OpenAI', host: 'api.openai.com', url: 'https://api.openai.com/v1', desc: 'Modelos da OpenAI com a sua chave de desenvolvedor.' },
  { id: 'openrouter', name: 'OpenRouter', host: 'openrouter.ai', url: 'https://openrouter.ai/api/v1', desc: 'Uma chave para modelos de vários laboratórios.' },
  { id: 'groq', name: 'Groq', host: 'api.groq.com', url: 'https://api.groq.com/openai/v1', desc: 'Modelos abertos servidos com resposta rápida.' },
  { id: 'gemini', name: 'Google Gemini', host: 'generativelanguage.googleapis.com', url: 'https://generativelanguage.googleapis.com/v1beta/openai', desc: 'Modelos Gemini pelo endpoint compatível com OpenAI.' },
];
const LOCAL = [
  { id: 'extractive', name: 'Só trechos', host: 'sem modelo', desc: 'A resposta são as frases das suas notas, cada uma com a fonte.' },
  { id: 'ollama', name: 'Ollama', host: 'localhost:11434', desc: 'Modelos rodando no seu computador. Nada sai da máquina.' },
  { id: 'lmstudio', name: 'LM Studio', host: 'localhost:1234', desc: 'Servidor local do LM Studio, com um modelo carregado.' },
];

const sameUrl = (a: string, b: string) => a.trim().replace(/\/+$/, '').toLowerCase() === b.toLowerCase();

export interface AnswerSourceValues {
  answer_provider: string;
  answer_base_url: string;
  answer_model?: string;
}

interface AiSourcesPaneProps {
  /** Provedor e URL do rascunho das configurações (o que está na tela, salvo ou não). */
  provider: string;
  baseUrl: string;
  keysConfigured: Record<string, boolean>;
  onUse: (values: AnswerSourceValues) => void;
  onKeySaved: () => void | Promise<void>;
}

const ListIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
    <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />
  </svg>
);

const Status = ({ tone, children }: { tone: 'ok' | 'idle'; children: string }) => (
  <span className={`ai-card__status ai-card__status--${tone}`}>
    <span aria-hidden="true" className="ai-card__dot" />
    {children}
  </span>
);

export const AiSourcesPane = ({ provider, baseUrl, keysConfigured, onUse, onKeySaved }: AiSourcesPaneProps) => {
  const [openId, setOpenId] = useState<string | null>(null);
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [found, setFound] = useState<ModelDiscoveryResult | null>(null);
  const [model, setModel] = useState('');
  const [consent, setConsent] = useState(false);

  const activeCloud = provider === 'openai-compatible' ? CLOUD.find((cloud) => sameUrl(baseUrl, cloud.url)) : undefined;
  const activeName = activeCloud?.name ?? LOCAL.find((local) => local.id === provider)?.name ?? 'API personalizada';
  const activeIsCloud = provider === 'openai-compatible';
  const isActive = (id: string) => provider === id || activeCloud?.id === id;

  const togglePanel = (id: string) => {
    setOpenId(openId === id ? null : id);
    setKey('');
    setFound(null);
    setModel('');
    setConsent(false);
  };

  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    try {
      await task();
    } finally {
      setBusy(false);
    }
  };

  const saveKey = (id: string) =>
    run(async () => {
      await bridge.saveApiKey(key, id);
      setKey('');
      await onKeySaved();
    });

  // Listar modelos já testa a chave: sem chave válida o provedor responde 401.
  const listModels = (url: string) =>
    run(async () => {
      const result = await bridge.listAnswerModels({ provider: 'openai-compatible', baseUrl: url });
      setFound(result);
      setModel(result.models[0]?.id ?? '');
    });

  const chooseCloud = (url: string) => {
    onUse({ answer_provider: 'openai-compatible', answer_base_url: url, answer_model: model });
    setOpenId(null);
  };

  return (
    <div className="ai-sources">
      <p className="ai-sources__now">
        Resposta do chat: <strong>{activeName}</strong>
        <span className={activeIsCloud ? 'ai-sources__where ai-sources__where--cloud' : 'ai-sources__where'}>
          {activeIsCloud ? 'na nuvem: pergunta e trechos saem do computador' : 'no computador'}
        </span>
      </p>

      <h4 className="ai-sources__group">No seu computador</h4>
      <div className="ai-sources__grid">
        {LOCAL.map((source) => (
          <article key={source.id} className={`ai-card${isActive(source.id) ? ' ai-card--active' : ''}`}>
            <div className="ai-card__body">
              <div className="ai-card__head">
                <span className="ai-card__logo">{source.id === 'extractive' ? <ListIcon /> : <ProviderLogo id={source.id} />}</span>
                <span className="ai-card__title">
                  <strong>{source.name}</strong>
                  <span className="ai-card__host">{source.host}</span>
                </span>
              </div>
              <p className="ai-card__desc">{source.desc}</p>
            </div>
            <div className="ai-card__foot">
              {isActive(source.id) ? (
                <span className="ai-card__inuse">Em uso</span>
              ) : (
                <button type="button" className="btn" onClick={() => onUse({ answer_provider: source.id, answer_base_url: '' })}>
                  Usar na resposta
                </button>
              )}
            </div>
          </article>
        ))}
      </div>

      <h4 className="ai-sources__group">Na nuvem, com a sua chave</h4>
      <p className="ai-sources__note" role="note">
        Com um provedor na nuvem, a sua pergunta e os trechos recuperados vão para o serviço escolhido. As notas inteiras
        nunca saem, e a chave fica salva só neste computador.
      </p>
      <div className="ai-sources__grid">
        {CLOUD.map((cloud) => {
          const configured = Boolean(keysConfigured[cloud.id]);
          const open = openId === cloud.id;
          return (
            <article key={cloud.id} className={`ai-card${isActive(cloud.id) ? ' ai-card--active' : ''}`}>
              <div className="ai-card__body">
                <div className="ai-card__head">
                  <span className="ai-card__logo">
                    <ProviderLogo id={cloud.id} />
                  </span>
                  <span className="ai-card__title">
                    <strong>{cloud.name}</strong>
                    <span className="ai-card__host">{cloud.host}</span>
                  </span>
                  <Status tone={configured ? 'ok' : 'idle'}>{configured ? 'Chave salva' : 'Sem chave'}</Status>
                </div>
                <p className="ai-card__desc">{cloud.desc}</p>
                {open && (
                  <div className="ai-card__panel">
                    <label className="ai-card__label" htmlFor={`chave-${cloud.id}`}>
                      Chave de API
                    </label>
                    <div className="ai-card__row">
                      <input
                        id={`chave-${cloud.id}`}
                        type="password"
                        className="vault-picker__input"
                        value={key}
                        autoComplete="off"
                        placeholder={configured ? 'Salva. Cole outra para trocar' : 'Cole a chave aqui'}
                        onChange={(event) => setKey(event.target.value)}
                      />
                      <button type="button" className="btn" disabled={busy || !key.trim()} onClick={() => saveKey(cloud.id)}>
                        Salvar chave
                      </button>
                    </div>
                    <button type="button" className="btn" disabled={busy || !configured} onClick={() => listModels(cloud.url)}>
                      {busy ? 'Testando…' : 'Testar e listar modelos'}
                    </button>
                    {found && (
                      <p role="status" className={found.status === 'ok' ? 'ai-card__ok' : 'settings-warning'}>
                        {found.status === 'ok'
                          ? `Conectado: ${found.models.length} modelos de conversa.`
                          : found.message ?? 'O provedor recusou a conexão. Confira a chave.'}
                      </p>
                    )}
                    {found && found.models.length > 0 && (
                      <>
                        <label className="ai-card__label" htmlFor={`modelo-${cloud.id}`}>
                          Modelo para a resposta
                        </label>
                        <select id={`modelo-${cloud.id}`} className="vault-picker__input" value={model} onChange={(event) => setModel(event.target.value)}>
                          {found.models.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </>
                    )}
                    <label className="ai-card__consent">
                      <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
                      Entendi que a pergunta e os trechos recuperados vão para o {cloud.name}.
                    </label>
                  </div>
                )}
              </div>
              <div className="ai-card__foot">
                {isActive(cloud.id) && <span className="ai-card__inuse">Em uso</span>}
                {open ? (
                  <button type="button" className="btn btn--primary" disabled={!model || !consent} onClick={() => chooseCloud(cloud.url)}>
                    Usar na resposta
                  </button>
                ) : (
                  <button type="button" className="btn" onClick={() => togglePanel(cloud.id)}>
                    {configured ? 'Gerenciar' : 'Conectar'}
                  </button>
                )}
                {open && (
                  <button type="button" className="btn" onClick={() => togglePanel(cloud.id)}>
                    Fechar
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <h4 className="ai-sources__group">Configuração manual</h4>
    </div>
  );
};
