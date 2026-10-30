"""Confere perguntas.json contra o texto normalizado das notas.

Para cada pergunta positiva verifica:
- cada expected_terms aparece na nota expected_note_id (mesma comparação case-insensitive do scorer);
- expected_ref aparece na nota;
- a nota existe.

Também registra, só como informação, se todos os termos cabem num mesmo chunk (800/120), que é o
critério de `_is_relevant` em pipeline/src/escolio/benchmark/runners.py, e a distância em caracteres
entre a primeira ocorrência do primeiro e do último termo.

Uso (a partir de pipeline/, para ter o pacote escolio):
    uv run python ../data/datasets/multi_trecho/checar_termos.py
Sai com código 1 se algum termo ou referência não for encontrado.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERGUNTAS = HERE / 'perguntas.json'
NOTAS = HERE / 'notas'


@dataclass
class ResultadoAmostra:
    sample_id: str
    category: str | None
    note_id: str | None
    missing: list[str] = field(default_factory=list)
    ref_found: bool = True
    single_chunk: bool | None = None
    spread_chars: int | None = None

    @property
    def ok(self) -> bool:
        return not self.missing and self.ref_found


def _note_text(note_id: str, cache: dict[str, str]) -> str:
    if note_id not in cache:
        from escolio.ingest.loaders import load_document
        from escolio.notes.structurer import structure_document

        note = structure_document(load_document(NOTAS / f'{note_id}.md'))
        cache[note_id] = note.normalized_text
    return cache[note_id]


def verificar(perguntas_path: Path = PERGUNTAS) -> list[ResultadoAmostra]:
    from escolio.retrieval.indexer import index_note
    from escolio.ingest.loaders import load_document
    from escolio.notes.structurer import structure_document

    payload = json.loads(perguntas_path.read_text(encoding='utf-8'))
    cache: dict[str, str] = {}
    resultados: list[ResultadoAmostra] = []
    for sample in payload['samples']:
        note_id = sample.get('expected_note_id')
        if note_id is None:
            continue
        texto = _note_text(note_id, cache)
        baixo = texto.lower()
        resultado = ResultadoAmostra(sample_id=sample['sample_id'], category=sample.get('category'), note_id=note_id)
        resultado.missing = [t for t in sample['expected_terms'] if t.lower() not in baixo]
        ref = sample.get('expected_ref')
        resultado.ref_found = ref is None or ref.lower() in baixo

        note = structure_document(load_document(NOTAS / f'{note_id}.md'))
        chunks = index_note(note, chunk_size=800, overlap=120)
        resultado.single_chunk = any(
            all(t.lower() in chunk.chunk_text.lower() for t in sample['expected_terms']) for chunk in chunks
        )
        posicoes = [baixo.find(t.lower()) for t in sample['expected_terms'] if t.lower() in baixo]
        if len(posicoes) >= 2:
            resultado.spread_chars = max(posicoes) - min(posicoes)
        resultados.append(resultado)
    return resultados


def main() -> int:
    resultados = verificar()
    falhas = [r for r in resultados if not r.ok]
    for r in resultados:
        status = 'OK  ' if r.ok else 'FAIL'
        extra = f' faltando={r.missing}' if r.missing else ''
        if not r.ref_found:
            extra += ' ref_nao_encontrada'
        print(
            f'{status} {r.sample_id:<12} {r.category or "-":<9} nota={r.note_id:<28} '
            f'mesmo_chunk={r.single_chunk} spread={r.spread_chars}{extra}'
        )
    total = len(resultados)
    print(f'\n{total - len(falhas)}/{total} perguntas positivas com termos e referência na nota esperada.')
    print(
        'Alcançáveis por um único chunk (800/120): '
        f'{sum(1 for r in resultados if r.single_chunk)}/{total}'
    )
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
