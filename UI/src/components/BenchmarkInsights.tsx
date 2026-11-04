import { useMemo, useState } from 'react';
import { discardText } from '../lib/discardReasons';
import { decidedRight, groupRows, matchesFilter, whyTiles, withAi, type RowFilter } from '../lib/benchmarkView';
import type { BenchmarkCompareResult, BenchmarkQueryRow } from '../services/bridge';
import './BenchmarkRun.css';

const hitsText = (row: BenchmarkQueryRow): string => {
  const notes = row.retrieved.slice(0, 3).map((hit) => hit.note_id ?? '').filter(Boolean);
  if (notes.length === 0) return 'nenhum';
  const unique = [...new Set(notes)];
  return unique.map((note) => {
    const count = notes.filter((other) => other === note).length;
    return count > 1 ? `${note} (${count} trechos)` : note;
  }).join(' · ');
};

const CHIPS: { id: RowFilter; label: string }[] = [
  { id: 'todas', label: 'Todas' },
  { id: 'certas', label: 'Certas' },
  { id: 'erradas', label: 'Erradas' },
];

/** Por que o chat errou e o mapa com cada pergunta: clicar num bloco acende as perguntas dele no mapa. */
const BenchmarkInsights = ({ result }: { result: BenchmarkCompareResult }) => {
  const rows = useMemo(() => result.corpus?.queries?.hybrid ?? [], [result]);
  const subtypes = useMemo(() => result.negative_subtypes ?? {}, [result]);
  const [filter, setFilter] = useState<RowFilter>('todas');
  const [mode, setMode] = useState<'decisao' | 'nota'>('decisao');
  const [selected, setSelected] = useState<string | null>(() => rows.find((row) => !decidedRight(row))?.sample_id ?? rows[0]?.sample_id ?? null);
  const tiles = useMemo(() => whyTiles(rows, subtypes), [rows, subtypes]);
  const groups = useMemo(() => groupRows(rows, mode), [rows, mode]);
  if (rows.length === 0) return null;
  const typed = tiles.length > 2;
  const row = rows.find((item) => item.sample_id === selected) ?? rows[0];
  const right = decidedRight(row);
  const lit = rows.filter((item) => matchesFilter(item, filter, subtypes)).length;
  const ai = withAi(result.answer_provider);

  return (
    <>
      <section className="card" aria-label="Por que errou">
        <div className="card__head"><h2>Por que errou</h2><span className="card__count">clique para ver no mapa</span></div>
        <div className="bench-why">
          {tiles.map((tile) => (
            <button
              key={tile.key}
              type="button"
              className={`bench-why__tile${tile.worst ? ' is-worst' : ''}`}
              aria-pressed={filter === tile.key}
              onClick={() => setFilter(filter === tile.key ? 'todas' : (tile.key as RowFilter))}
            >
              <span className="bench-why__title">{tile.title}{tile.worst && <em>mais fraco</em>}</span>
              <b className="mono">{tile.count} de {tile.total}</b>
              <span className="bench-why__track"><span style={{ width: `${tile.total ? (tile.count / tile.total) * 100 : 0}%` }} /></span>
              <span className="bench-why__text">{tile.text}</span>
            </button>
          ))}
          {!typed && <p className="bench-why__note">Esta suíte não marca o tipo das perguntas sem resposta. No lote cego, elas vêm separadas em quase certas, mesmas palavras e fora do assunto.</p>}
        </div>
      </section>

      <div className="bench-pair bench-pair--map">
        <section className="card" aria-label="Mapa das perguntas">
          <div className="card__head"><h2>Mapa das perguntas</h2><span className="card__count">{lit} de {rows.length}</span></div>
          <div className="bench-map__tools">
            <div className="bench-chips" role="group" aria-label="Filtrar perguntas">
              {CHIPS.map((chip) => (
                <button key={chip.id} type="button" className="bench-chip" aria-pressed={filter === chip.id} onClick={() => setFilter(chip.id)}>{chip.label}</button>
              ))}
            </div>
            <div className="bench-chips" role="group" aria-label="Agrupar perguntas">
              <button type="button" className="bench-chip" aria-pressed={mode === 'decisao'} onClick={() => setMode('decisao')}>Por decisão</button>
              <button type="button" className="bench-chip" aria-pressed={mode === 'nota'} onClick={() => setMode('nota')}>Por nota</button>
            </div>
          </div>
          <div className="bench-map__scroll" tabIndex={0} role="group" aria-label="Perguntas">
            {groups.map((group) => (
              <div key={group.name} className={mode === 'nota' ? 'bench-map__line' : 'bench-map__stack'}>
                <b className="bench-map__name"><span title={group.name}>{group.name}</span><span className="mono">{group.rows.filter(decidedRight).length}/{group.rows.length}</span></b>
                <div className="bench-map__cells">
                  {group.rows.map((item) => {
                    const on = matchesFilter(item, filter, subtypes);
                    return (
                      <button
                        key={item.sample_id}
                        type="button"
                        className={`bench-cell ${decidedRight(item) ? 'is-ok' : 'is-err'}${on ? '' : ' is-dim'}${item.sample_id === row.sample_id ? ' is-sel' : ''}`}
                        aria-label={item.question}
                        aria-pressed={item.sample_id === row.sample_id}
                        title={item.question}
                        onClick={() => setSelected(item.sample_id)}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <div className="bench-map__legend">
            <span><i className="bench-cell is-ok" aria-hidden="true" />decisão certa</span>
            <span><i className="bench-cell is-err" aria-hidden="true" />decisão errada</span>
          </div>
        </section>

        <section className="card" aria-label="Pergunta selecionada">
          <div className="card__head">
            <h2>Pergunta selecionada</h2>
            <span className={`bench-mark bench-mark--${right ? 'ok' : 'err'}`}>{row.answered ? 'Respondeu' : 'Recusou'}, {right ? 'certo' : 'errado'}</span>
          </div>
          <div className="bench-detail" tabIndex={0} role="group" aria-label="Detalhes da pergunta">
            <p className="bench-detail__q">{row.question}</p>
            <dl>
              {ai && row.answered && (
                <div><dt>De onde veio</dt><dd>{row.generated ? 'Escrita pela IA a partir dos trechos.' : `Trecho original das notas.${row.discard_reason ? ` IA descartada: ${discardText(row.discard_reason)}` : ''}`}</dd></div>
              )}
              {row.expected_ref && <div><dt>Esperado</dt><dd>{row.expected_note_id} · {row.expected_ref}</dd></div>}
              <div><dt>O chat disse</dt><dd>{row.answer || (row.answered ? 'Esta rodada não guardou o texto da resposta.' : 'Não encontrei isso no vault.')}</dd></div>
              <div><dt>Trechos achados</dt><dd className="mono">{hitsText(row)}</dd></div>
            </dl>
          </div>
        </section>
      </div>
    </>
  );
};

export default BenchmarkInsights;
