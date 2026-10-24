"""Confere perguntas.json contra o texto normalizado das notas de multi_trecho.

Adaptação de data/datasets/multi_trecho/checar_termos.py para o lote de cobertura, em que uma
pergunta pode juntar termos de duas notas. Para cada pergunta verifica:
- expected_terms_por_nota: cada termo aparece na nota indicada (comparação case-insensitive, a
  mesma do scorer);
- expected_terms é a união de expected_terms_por_nota, sem termo sobrando;
- expected_ref aparece na nota primária;
- mt-nota-*: nenhum chunk 800/120 contém todos os termos (a pergunta exige juntar chunks);
- mt-notas-*: os termos vêm de pelo menos duas notas distintas.

Também registra, só como informação, a distância em caracteres entre a primeira ocorrência do
primeiro e do último termo da nota primária.

Uso (a partir de pipeline/, para ter o pacote escolio):
    uv run python ../data/datasets/multi_trecho_cobertura/checar_termos.py
Sai com código 1 se alguma verificação falhar.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERGUNTAS = HERE / 'perguntas.json'
NOTAS = HERE.parent / 'multi_trecho' / 'notas'


@dataclass
class ResultadoAmostra:
    sample_id: str
    note_id: str | None
    erros: list[str] = field(default_factory=list)
    single_chunk: bool | None = None
    spread_chars: int | None = None

    @property
    def ok(self) -> bool:
        return not self.erros


def _note_text(note_id: str, cache: dict[str, str]) -> str:
    if note_id not in cache:
        from escolio.ingest.loaders import load_document
        from escolio.notes.structurer import structure_document

        note = structure_document(load_document(NOTAS / f'{note_id}.md'))
        cache[note_id] = note.normalized_text
    return cache[note_id]


def verificar(perguntas_path: Path = PERGUNTAS) -> list[ResultadoAmostra]:
    from escolio.ingest.loaders import load_document
    from escolio.notes.structurer import structure_document
    from escolio.retrieval.indexer import index_note

    payload = json.loads(perguntas_path.read_text(encoding='utf-8'))
    cache: dict[str, str] = {}
    resultados: list[ResultadoAmostra] = []
    for sample in payload['samples']:
        primaria = sample['expected_note_id']
        por_nota: dict[str, list[str]] = sample['expected_terms_por_nota']
        resultado = ResultadoAmostra(sample_id=sample['sample_id'], note_id=primaria)

        uniao = [termo for termos in por_nota.values() for termo in termos]
        if sorted(uniao) != sorted(sample['expected_terms']):
            resultado.erros.append('expected_terms difere da união de expected_terms_por_nota')
        if primaria not in por_nota:
            resultado.erros.append('nota primária ausente em expected_terms_por_nota')

        for note_id, termos in por_nota.items():
            texto = _note_text(note_id, cache).lower()
            faltando = [t for t in termos if t.lower() not in texto]
            if faltando:
                resultado.erros.append(f'{note_id}: faltando {faltando}')

        texto_primaria = _note_text(primaria, cache)
        ref = sample.get('expected_ref')
        if ref and ref.lower() not in texto_primaria.lower():
            resultado.erros.append(f'ref {ref!r} ausente na nota primária')

        tipo = sample['sample_id'].rsplit('-', 1)[0]
        if tipo == 'mt-notas' and len(por_nota) < 2:
            resultado.erros.append('mt-notas precisa de termos de pelo menos duas notas')
        if tipo == 'mt-nota' and len(por_nota) != 1:
            resultado.erros.append('mt-nota precisa de termos de uma única nota')

        if tipo == 'mt-nota':
            note = structure_document(load_document(NOTAS / f'{primaria}.md'))
            chunks = index_note(note, chunk_size=800, overlap=120)
            resultado.single_chunk = any(
                all(t.lower() in chunk.chunk_text.lower() for t in sample['expected_terms']) for chunk in chunks
            )
            if resultado.single_chunk:
                resultado.erros.append('mt-nota cabe num único chunk 800/120 (não junta trechos)')

        posicoes = [texto_primaria.lower().find(t.lower()) for t in por_nota.get(primaria, [])]
        posicoes = [p for p in posicoes if p >= 0]
        if len(posicoes) >= 2:
            resultado.spread_chars = max(posicoes) - min(posicoes)
        resultados.append(resultado)
    return resultados


def main() -> int:
    resultados = verificar()
    falhas = [r for r in resultados if not r.ok]
    for r in resultados:
        status = 'OK  ' if r.ok else 'FAIL'
        extra = f' {r.erros}' if r.erros else ''
        print(
            f'{status} {r.sample_id:<12} nota={r.note_id:<28} '
            f'mesmo_chunk={r.single_chunk} spread={r.spread_chars}{extra}'
        )
    total = len(resultados)
    print(f'\n{total - len(falhas)}/{total} perguntas com termos, referência e junção conferidos.')
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
