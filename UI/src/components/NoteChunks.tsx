import { useEffect, useRef, useState } from 'react';
import type { NoteChunkSummary } from '../services/bridge';
import { plainMarkdown } from '../lib/plainMarkdown';

interface NoteChunksProps {
  chunks: NoteChunkSummary[];
  /** Trecho citado numa resposta do chat: fica destacado e a tela rola até ele. */
  highlightChunkId: string | null;
}

const fmt = (value: number) => value.toLocaleString('pt-BR');

/** Trechos da nota: o mapa de onde cada um cai no texto e os cartões, com os dados dentro de cada um. */
export const NoteChunks = ({ chunks, highlightChunkId }: NoteChunksProps) => {
  const [active, setActive] = useState<number | null>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const citedRef = useRef<HTMLLIElement>(null);
  const total = Math.max(0, ...chunks.map((chunk) => chunk.char_end));

  useEffect(() => {
    citedRef.current?.scrollIntoView({ block: 'center' });
  }, []);

  if (chunks.length === 0) return <p className="reader__nochunks">Esta nota ainda não tem trechos indexados.</p>;

  const goTo = (index: number) => {
    setActive(index);
    listRef.current?.children[index]?.scrollIntoView({ block: 'center' });
  };

  return (
    <>
      {total > 0 && (
        <section className="chunk-map" aria-label="Mapa dos trechos">
          <div className="chunk-map__head">
            <b>Onde cada trecho cai na nota</b>
            <span className="mono">{fmt(total)} caracteres</span>
          </div>
          <div className="chunk-map__track">
            {chunks.map((chunk, i) => (
              <button
                key={chunk.chunk_id}
                type="button"
                className={`chunk-map__seg${i % 2 ? ' chunk-map__seg--low' : ''}${active === i ? ' is-on' : ''}`}
                aria-label={`Ir para o trecho ${chunk.chunk_index}`}
                style={{
                  left: `${((chunk.char_start / total) * 100).toFixed(2)}%`,
                  width: `${(((chunk.char_end - chunk.char_start) / total) * 100).toFixed(2)}%`,
                }}
                onClick={() => goTo(i)}
              />
            ))}
          </div>
          {chunks.length > 1 && <p>As faixas se cruzam onde há sobreposição: esse pedaço entra em dois trechos.</p>}
        </section>
      )}

      <ol ref={listRef} className="reader__chunks" aria-label="Trechos indexados">
        {chunks.map((chunk, i) => {
          const overlap = i > 0 ? chunks[i - 1].char_end - chunk.char_start : 0;
          const cited = chunk.chunk_id === highlightChunkId;
          return (
            <li
              key={chunk.chunk_id}
              ref={cited ? citedRef : undefined}
              className={`reader__chunk${cited ? ' reader__chunk--cited' : ''}${active === i ? ' is-active' : ''}`}
              title={chunk.chunk_id}
            >
              <div className="reader__chunk-head mono">
                <b>#{chunk.chunk_index}</b>
                <span>{chunk.token_count} tok</span>
                <span>{fmt(chunk.char_start)}–{fmt(chunk.char_end)}</span>
                {overlap > 0 && <span className="reader__chunk-overlap">↥ {overlap} sobrepostos</span>}
                {cited && <span className="reader__chunk-cited">trecho citado</span>}
              </div>
              {/* Só a exibição perde o Markdown cru; snippet, offsets e contagens seguem como vieram. */}
              <p style={{ whiteSpace: 'pre-line' }}>{plainMarkdown(chunk.snippet)}</p>
            </li>
          );
        })}
      </ol>
    </>
  );
};
