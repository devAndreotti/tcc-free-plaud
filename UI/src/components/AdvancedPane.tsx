import { useEffect, useRef, useState, type ReactNode } from 'react';
import { bridge, type SettingRow, type SettingPreset, type SettingPresetResult } from '../services/bridge';
import { Glyph, GlyphBadge, type GlyphName } from './ui/Glyph';
import { GroupCard, SectionHead } from './ui/Controls';
import { ChunkArt, SearchArt, VectorArt } from './AdvancedArt';

// Grupos do catálogo (app/settings_specs.py) com nome, ícone e uma linha de apoio.
const GROUPS: Record<string, { title: string; icon: GlyphName; desc: string }> = {
  Retrieval: { title: 'Busca', icon: 'search', desc: 'Como cada pergunta encontra os trechos.' },
  Embeddings: { title: 'Busca semântica', icon: 'graph', desc: 'Onde o modelo de vetores roda.' },
  Chunks: { title: 'Trechos', icon: 'scissors', desc: 'Como as notas são cortadas. Mudar exige reindexar.' },
  Corpus: { title: 'Indexação', icon: 'layers', desc: 'Ritmo da Fila ao indexar pastas.' },
  LLM: { title: 'Resposta da IA', icon: 'stars', desc: 'Vale para Ollama, LM Studio e provedores na nuvem.' },
};

const ORDER = Object.keys(GROUPS);
const groupOrder = (group: string) => (ORDER.includes(group) ? ORDER.indexOf(group) : ORDER.length);
const valueOf = (catalog: SettingRow[], key: string) => catalog.find((row) => row.key === key)?.value;

const PRESET_ICONS: [RegExp, GlyphName][] = [[/cpu/i, 'cpu'], [/gpu/i, 'gpu'], [/grande|large/i, 'layers'], [/tcc|reprodut/i, 'cap']];
const presetIcon = (preset: SettingPreset): GlyphName => PRESET_ICONS.find(([re]) => re.test(`${preset.key} ${preset.label}`))?.[1] ?? 'boxes';

const INSIDE: [GlyphName, string][] = [['boxes', 'Presets prontos'], ['search', 'Busca'], ['graph', 'Busca semântica'], ['scissors', 'Trechos'], ['layers', 'Indexação'], ['stars', 'Resposta da IA']];

/** Aba Avançado bloqueada: explica o que tem dentro e libera com uma animação (cadeado abre, controles deslizam). */
export const AdvancedLocked = ({ onUnlock }: { onUnlock: () => void }) => {
  const [agree, setAgree] = useState(false);
  const [opening, setOpening] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const unlock = () => {
    if (!agree || opening) return;
    setOpening(true);
    timer.current = window.setTimeout(onUnlock, 1000);
  };

  return (
    <section className={`settings-section adv-lock${opening ? ' adv-lock--opening' : ''}`} aria-labelledby="settings-advanced">
      <SectionHead icon="code" id="settings-advanced" title="Avançado" lede="Ajustes finos de busca, trechos, indexação e resposta da IA." />
      <div className="adv-lock__hero rise">
        <svg className="adv-lock__art" viewBox="0 0 200 160" fill="none" stroke="currentColor" strokeLinecap="round" aria-hidden="true" focusable="false">
          <rect x="12" y="22" width="166" height="126" rx="16" fill="currentColor" fillOpacity=".04" strokeOpacity=".35" strokeWidth="1.5" />
          {[[58, 88, 'k1'], [90, 128, 'k2'], [122, 64, 'k3']].map(([y, x, k]) => (
            <g key={k}>
              <path d={`M38 ${y}H152`} strokeOpacity=".25" strokeWidth="4" />
              <path className={`adv-lock__fill adv-lock__fill--${k}`} d={`M38 ${y}H${x}`} strokeWidth="4" />
              <circle className={`adv-lock__knob adv-lock__knob--${k}`} cx={x} cy={y} r="8" fill="var(--bg-panel)" strokeWidth="2.5" />
            </g>
          ))}
          <circle className="adv-lock__ring" cx="170" cy="28" r="23" strokeWidth="2" />
          <circle cx="170" cy="28" r="23" fill="var(--bg-panel)" strokeWidth="2" />
          <rect x="160" y="27" width="20" height="15" rx="3.5" strokeWidth="2" />
          <path className="adv-lock__shackle" d="M164 27v-4a6 6 0 0 1 12 0v4" strokeWidth="2" />
        </svg>
        <div className="adv-lock__text">
          <span className="pill">Bloqueado</span>
          <h4>Para quem já conhece o efeito de cada ajuste</h4>
          <p>Estes ajustes mudam como a busca encontra os trechos e como as pastas viram índice. Um valor errado piora as respostas ou obriga a reindexar a vault.</p>
          <ul aria-label="O que tem no Avançado">
            {INSIDE.map(([icon, label]) => (
              <li key={label}>
                <Glyph name={icon} size={14} />
                {label}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="adv-lock__confirm rise" style={{ animationDelay: '80ms' }}>
        <label className="adv-lock__agree">
          <input type="checkbox" checked={agree} onChange={(event) => setAgree(event.target.checked)} disabled={opening} />
          <span>Entendo que estes ajustes podem piorar as respostas e que alguns só valem depois de reindexar.</span>
        </label>
        <div className="adv-lock__go">
          <button type="button" className="btn btn--primary ui-press" onClick={unlock} disabled={!agree || opening}>
            <Glyph name="unlock" size={16} />
            Mostrar ajustes avançados
          </button>
          <span>Fica liberado só neste computador. Dá para esconder de novo na própria aba.</span>
        </div>
      </div>
    </section>
  );
};

interface AdvancedPaneProps {
  presets: SettingPreset[];
  rows: SettingRow[];
  catalog: SettingRow[];
  /** Estratégia escolhida no seletor, ainda não salva; o desenho da Busca acompanha. */
  strategy?: string;
  hiddenKeys: string[];
  applyingPreset: string;
  pendingChanges: number;
  catalogLabel: (key: string) => string;
  renderRow: (row: SettingRow) => ReactNode;
  onApplyPreset: (key: string) => void;
  onHide: () => void;
}

/** Preset em uso: todos os valores dele batem com os salvos. */
const presetInUse = (preset: SettingPreset, catalog: SettingRow[]) =>
  Object.entries(preset.values).every(([key, value]) => {
    const row = catalog.find((item) => item.key === key);
    return row ? String(row.value) === String(value) : false;
  });

// Prévia de um preset: o que muda antes de aplicar. Nada é gravado aqui.
type PresetPreview = { key: string; status: 'loading' | 'ready' | 'error'; result?: SettingPresetResult; error?: string };

// O preset nunca troca o modelo de busca da vault: o backend também não o grava (apply_settings_preset exclui embedding_model).
const EMBEDDING_KEY = 'embedding_model';
const formatValue = (value: string | number | boolean | null | undefined) => (value === null || value === undefined ? '—' : String(value));

export const AdvancedPane = ({ presets, rows, catalog, strategy, hiddenKeys, applyingPreset, pendingChanges, catalogLabel, renderRow, onApplyPreset, onHide }: AdvancedPaneProps) => {
  const [preview, setPreview] = useState<PresetPreview | null>(null);
  // Respostas da prévia que chegam depois de cancelar (ou de abrir outra) são ignoradas.
  const previewKey = useRef('');
  const groups = rows.reduce<Record<string, SettingRow[]>>((acc, row) => {
    (acc[row.group] ??= []).push(row);
    return acc;
  }, {});

  const openPreview = (key: string) => {
    previewKey.current = key;
    setPreview({ key, status: 'loading' });
    bridge.previewSettingsPreset(key)
      .then((result) => {
        if (previewKey.current === key) setPreview({ key, status: 'ready', result });
      })
      .catch((error: unknown) => {
        if (previewKey.current === key) {
          setPreview({ key, status: 'error', error: error instanceof Error ? error.message : 'erro desconhecido' });
        }
      });
  };

  const closePreview = () => {
    previewKey.current = '';
    setPreview(null);
  };

  const confirmPreview = (key: string) => {
    closePreview();
    onApplyPreset(key);
  };

  const renderPreview = (preset: SettingPreset) => {
    if (preview?.status === 'loading') {
      return <p className="adv-preview__status" role="status">Calculando a prévia…</p>;
    }
    if (preview?.status === 'error') {
      return (
        <div className="adv-preview">
          <p className="adv-preview__error" role="alert">Não foi possível montar a prévia: {preview.error}</p>
          <div className="adv-preview__actions">
            <button type="button" className="btn btn--sm ui-press" onClick={closePreview}>Cancelar</button>
          </div>
        </div>
      );
    }
    const changes = preview?.result?.changes ?? {};
    return (
      <div className="adv-preview" aria-label={`Prévia do preset ${preset.label}`}>
        {Object.keys(changes).length === 0 ? (
          <p className="adv-preview__status">Nenhum valor muda com este preset.</p>
        ) : (
          <ul className="adv-preview__list" aria-label="O que muda">
            {Object.entries(changes).map(([key, change]) => (
              <li key={key}>
                <span>{key === 'embedding_model' ? 'Modelo de busca semântica' : catalogLabel(key)}</span>
                <span className="mono">{formatValue(change.before)}</span>
                <span aria-hidden="true">→</span>
                <span className="mono">{formatValue(change.after)}</span>
              </li>
            ))}
          </ul>
        )}
        {EMBEDDING_KEY in changes && (
          <p className="adv-preview__note" role="note">
            O modelo de busca é fixo por vault: esta vault continua com o modelo atual. O novo vale para vaults criadas depois.
          </p>
        )}
        <div className="adv-preview__actions">
          <button type="button" className="btn btn--sm ui-press" onClick={closePreview}>Cancelar</button>
          <button type="button" className="btn btn--sm btn--primary ui-press" onClick={() => confirmPreview(preset.key)} disabled={Boolean(applyingPreset)}>
            Aplicar
          </button>
        </div>
      </div>
    );
  };

  return (
    <>
      <section className="settings-section" aria-labelledby="settings-advanced">
        <SectionHead icon="code" id="settings-advanced" title="Avançado" lede="Ajustes finos de busca, trechos, indexação e resposta da IA. Mude só se souber o efeito.">
          <button type="button" className="btn btn--sm ui-press" onClick={onHide}>
            <Glyph name="eyeOff" size={15} />
            Ocultar Avançado
          </button>
        </SectionHead>
        <h4 className="adv-sub" id="settings-presets">Presets <span>Aplicar grava na hora.</span></h4>
        <div className="ui-grid adv-presets">
          {presets.map((preset, i) => {
            const inUse = presetInUse(preset, catalog);
            const busy = applyingPreset === preset.key;
            return (
              <article key={preset.key} className={`adv-preset ui-card rise lift${inUse ? ' adv-preset--on' : ''}`} style={{ animationDelay: `${i * 60}ms` }} aria-label={preset.label}>
                <div className="adv-preset__head">
                  <GlyphBadge name={presetIcon(preset)} size={40} />
                  <div>
                    <strong>{preset.label}</strong>
                    {inUse && <span className="pill pill--accent pop">Em uso</span>}
                    <p>{preset.description}</p>
                  </div>
                </div>
                <dl className="adv-preset__values">
                  {Object.entries(preset.values)
                    .filter(([key]) => !hiddenKeys.includes(key))
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{catalogLabel(key)}</dt>
                        <dd className="mono">{String(value)}</dd>
                      </div>
                    ))}
                </dl>
                {preview?.key === preset.key ? renderPreview(preset) : (
                  <div className="adv-preset__foot">
                    {busy ? (
                      <span className="adv-preset__busy" role="status">
                        <span className="adv-preset__spinner ui-spin" aria-hidden="true" />
                        Aplicando…
                      </span>
                    ) : inUse ? (
                      <span className="adv-preset__done pop">
                        <Glyph name="check" size={14} strokeWidth={2.2} />
                        Aplicado
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="btn btn--sm ui-press"
                        onClick={() => openPreview(preset.key)}
                        disabled={Boolean(applyingPreset) || pendingChanges > 0}
                        title={pendingChanges > 0 ? 'Salve ou descarte antes de aplicar' : undefined}
                        aria-label={`Aplicar preset ${preset.label}`}
                      >
                        Aplicar
                      </button>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="settings-section" aria-label="Ajustes avançados">
        <h4 className="adv-sub">Ajustes</h4>
        <div className="ui-grid">
          {Object.entries(groups)
            .sort(([a], [b]) => groupOrder(a) - groupOrder(b))
            .map(([group, groupRows], i) => {
              const meta = GROUPS[group] ?? { title: group, icon: 'sliders' as GlyphName, desc: '' };
              const art =
                group === 'Retrieval' ? <SearchArt strategy={strategy || String(valueOf(catalog, 'default_ask_strategy') ?? 'hybrid')} /> :
                group === 'Embeddings' ? <VectorArt /> :
                group === 'Chunks' ? <ChunkArt size={Number(valueOf(catalog, 'default_chunk_size') ?? 800)} overlap={Number(valueOf(catalog, 'default_chunk_overlap') ?? 120)} /> :
                null;
              return (
                <GroupCard key={group} icon={meta.icon} title={meta.title} desc={meta.desc} delay={200 + i * 60} className={`adv-group${group === 'LLM' ? ' adv-group--wide' : ''}`}>
                  {art}
                  <div className="adv-group__rows">{groupRows.map((row) => renderRow(row))}</div>
                </GroupCard>
              );
            })}
        </div>
      </section>
    </>
  );
};
