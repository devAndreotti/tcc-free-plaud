import { useRef, useState } from 'react';
import { bridge, type BackendSettings, type ModelInfo } from '../services/bridge';
import { useDismissOnOutside } from '../hooks/useDismissOnOutside';
import { CheckIcon, ChevronDownIcon, ListIcon, SparkleIcon } from './Icons';

const EXTRACTIVE = 'extractive';
// Onde listar os modelos quando a resposta está só em trechos: o Ollama é o provedor local padrão.
const DEFAULT_PROVIDER = 'ollama';

// "qchat:latest" aparece como "qchat". O recomendado é o ajuste do projeto para a GPU de 4 GB.
const displayName = (id: string) => id.replace(/:latest$/, '');
const isRecommended = (id: string) => displayName(id) === 'qchat';
const isEmbedding = (id: string) => id.includes('embed');

interface AnswerPickerProps {
  /** Provedor salvo: 'extractive' (só trechos) ou o generativo, como 'ollama'. */
  provider: string;
  /** Modelo salvo, como 'qchat:latest'. */
  model: string | null;
  /** Recebe a configuração que o backend devolveu ao salvar. */
  onSaved: (settings: BackendSettings) => void;
}

/** Pílula de resposta da barra: escolhe só trechos ou um modelo instalado, e salva como a aba IA faz. */
export const AnswerPicker = ({ provider, model, onSaved }: AnswerPickerProps) => {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<ModelInfo[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);
  useDismissOnOutside(open, wrapRef, () => setOpen(false));

  const isAi = provider !== EXTRACTIVE;
  const listProvider = isAi ? provider : DEFAULT_PROVIDER;
  const label = isAi ? (model ? displayName(model) : 'IA') : 'Só trechos';
  const isSelected = (id: string) => isAi && model !== null && displayName(id) === displayName(model);
  // O backend já tira os modelos de embedding; o filtro aqui só garante que nenhum escapa.
  const options = (models ?? [])
    .filter((item) => !isEmbedding(item.id))
    .sort((a, b) => Number(isRecommended(b.id)) - Number(isRecommended(a.id)));

  const toggle = () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setModels(null);
    bridge
      .listAnswerModels({ provider: listProvider })
      .then((result) => setModels(result.models))
      .catch(() => setModels([]));
  };

  const choose = async (nextProvider: string, nextModel: string | null) => {
    if (saving) return;
    setSaving(true);
    setError('');
    try {
      const values: Record<string, string> =
        nextProvider === EXTRACTIVE
          ? { answer_provider: EXTRACTIVE }
          : { answer_provider: nextProvider, answer_model: nextModel ?? '' };
      onSaved(await bridge.saveBackendSettings(values));
      setOpen(false);
    } catch (err) {
      console.error('[AnswerPicker] Erro ao salvar a resposta:', err);
      setError('Não foi possível salvar a escolha. Tente de novo.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="strategy" ref={wrapRef}>
      <button
        type="button"
        className={`strategy__chip answer__chip${isAi ? ' answer__chip--ai' : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Como responder: ${label}`}
        onClick={toggle}
      >
        {isAi ? (
          <>
            {/* ponytail: sem estado de "aquecido" no backend (warmAnswerModel só devolve ok/started); a bolinha fica cinza até o status ser exposto. */}
            <span className="answer__dot" aria-hidden="true" />
            <SparkleIcon size={15} />
          </>
        ) : (
          <ListIcon size={15} />
        )}
        {label}
        {isAi && <span className="answer__badge">IA</span>}
        <ChevronDownIcon size={13} />
      </button>
      {open && (
        <div className="strategy__menu answer__menu">
          <div role="listbox" aria-label="Como responder" aria-busy={saving}>
            <button
              type="button"
              role="option"
              aria-selected={!isAi}
              className="answer__item"
              disabled={saving}
              onClick={() => void choose(EXTRACTIVE, null)}
            >
              <ListIcon size={16} />
              <span>
                <span className="answer__title">Só trechos</span>
                <small>Sem modelo. Resposta na hora.</small>
              </span>
              {!isAi && <CheckIcon size={15} />}
            </button>
            {options.map((item) => {
              const recommended = isRecommended(item.id);
              const detail = recommended
                ? 'Qwen 2.5 3B ajustado. Cabe na GPU de 4 GB.'
                : [item.details.parameter_size, item.details.quantization_level].filter(Boolean).join(' · ');
              const selected = isSelected(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className="answer__item"
                  disabled={saving}
                  onClick={() => void choose(listProvider, item.id)}
                >
                  <SparkleIcon size={16} />
                  <span>
                    <span className="answer__title">
                      {displayName(item.id)}
                      {recommended && <span className="answer__tag">recomendado</span>}
                    </span>
                    {detail && <small>{detail}</small>}
                  </span>
                  {selected && <CheckIcon size={15} />}
                </button>
              );
            })}
          </div>
          {models === null && <p className="answer__status">Listando modelos…</p>}
          {models !== null && options.length === 0 && <p className="answer__status">Nenhum modelo de conversa instalado.</p>}
          {error && <p className="answer__status answer__status--error" role="alert">{error}</p>}
          <div className="answer__legend">
            <span>
              <i className="answer__dot answer__dot--on" aria-hidden="true" />
              na memória, responde na hora
            </span>
            <span>
              <i className="answer__dot answer__dot--off" aria-hidden="true" />
              carrega na primeira pergunta (cerca de 8 s)
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
