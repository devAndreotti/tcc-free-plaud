"""Cobertura de termos somada entre os k primeiros trechos.

Complementa `_is_relevant` (benchmark/runners.py), que só aceita um chunk que contenha todos os
`expected_terms`. Numa pergunta que junta dois trechos, a cobertura mede se a união do top-k tem
todos os termos, mesmo que nenhum chunk isolado os tenha. Funções puras: não mudam o scorer nem
as métricas existentes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from escolio.benchmark.metrics import bootstrap_ci
from escolio.retrieval.search import _strip_accents

GRUPOS_CONHECIDOS = ('unica', 'mt-nota', 'mt-notas')
GRUPO_TODOS = 'todos'


def grupo_da_pergunta(sample_id: str) -> str:
    """Grupo pelo prefixo do sample_id. `mt-notas` vem antes de `mt-nota` para não casar errado."""
    for grupo in ('mt-notas', 'mt-nota', 'unica'):
        if sample_id == grupo or sample_id.startswith(f'{grupo}-'):
            return grupo
    return 'outro'


def normalizar_texto(texto: str) -> str:
    """Sem acento, minúsculas e espaços colapsados, para comparar termos com o texto dos trechos."""
    return ' '.join(_strip_accents(texto).lower().split())


def _cobertos(expected_terms: Sequence[str], chunk_texts: Sequence[str], k: int) -> tuple[int, int]:
    if k < 1:
        raise ValueError('k deve ser pelo menos 1.')
    if not expected_terms:
        raise ValueError('expected_terms vazio: a cobertura não se define sem termos.')
    termos = [normalizar_texto(termo) for termo in expected_terms]
    if any(not termo for termo in termos):
        raise ValueError('expected_terms com termo vazio depois da normalização.')
    uniao = normalizar_texto('\n'.join(chunk_texts[:k]))
    return sum(1 for termo in termos if termo in uniao), len(termos)


def term_coverage_at_k(expected_terms: Sequence[str], chunk_texts: Sequence[str], k: int) -> float:
    """Fração dos termos presentes na união dos k primeiros trechos (na ordem do ranking)."""
    cobertos, total = _cobertos(expected_terms, chunk_texts, k)
    return cobertos / total


def joined_hit_at_k(expected_terms: Sequence[str], chunk_texts: Sequence[str], k: int) -> int:
    """1 quando a união do top-k cobre todos os termos (junção completa), senão 0."""
    cobertos, total = _cobertos(expected_terms, chunk_texts, k)
    return 1 if cobertos == total else 0


def trechos_do_ranking(
    retrieved: Iterable[Mapping[str, object]],
    textos_por_nota: Mapping[str, str],
) -> list[str]:
    """Texto de cada trecho do ranking, reconstruído pelos offsets char_start/char_end.

    O JSON do compare grava os offsets, não o texto. Os offsets são relativos ao texto da nota já
    com `.strip()`, o mesmo que `chunk_text` usa no chunking. Nota fora do mapa é erro, não zero:
    trecho sem texto subestimaria a cobertura sem aviso.
    """
    trechos: list[str] = []
    for hit in sorted(retrieved, key=lambda item: int(str(item['rank']))):
        nota = str(hit['note_id'])
        if nota not in textos_por_nota:
            raise ValueError(f'nota {nota!r} do ranking não está na suite; não dá para reconstruir o trecho.')
        texto = textos_por_nota[nota]
        inicio, fim = int(str(hit['char_start'])), int(str(hit['char_end']))
        if not 0 <= inicio < fim <= len(texto):
            raise ValueError(f'offsets {inicio}:{fim} fora do texto da nota {nota!r} ({len(texto)} caracteres).')
        trechos.append(texto[inicio:fim])
    return trechos


@dataclass(frozen=True)
class CoverageRow:
    """Cobertura de uma pergunta numa estratégia, para cada profundidade k."""

    strategy: str
    sample_id: str
    coverage: dict[int, float] = field(default_factory=dict)
    joined: dict[int, int] = field(default_factory=dict)

    @property
    def grupo(self) -> str:
        return grupo_da_pergunta(self.sample_id)


def build_coverage_row(
    strategy: str,
    sample_id: str,
    expected_terms: Sequence[str],
    chunk_texts: Sequence[str],
    ks: Iterable[int],
) -> CoverageRow:
    coverage: dict[int, float] = {}
    joined: dict[int, int] = {}
    for k in ks:
        coverage[k] = term_coverage_at_k(expected_terms, chunk_texts, k)
        joined[k] = joined_hit_at_k(expected_terms, chunk_texts, k)
    return CoverageRow(strategy=strategy, sample_id=sample_id, coverage=coverage, joined=joined)


def coverage_summary(rows: Sequence[CoverageRow]) -> list[dict[str, object]]:
    """Uma célula por (estratégia, grupo, k): média e IC 95% bootstrap da cobertura e da junção.

    O grupo `todos` agrega as perguntas de todos os grupos e sai junto dos separados.
    """
    cells: list[dict[str, object]] = []
    estrategias = sorted({row.strategy for row in rows})
    ks = sorted({k for row in rows for k in row.coverage})
    for strategy in estrategias:
        do_strategy = [row for row in rows if row.strategy == strategy]
        grupos = sorted({row.grupo for row in do_strategy})
        for grupo in [*grupos, GRUPO_TODOS]:
            selecionadas = do_strategy if grupo == GRUPO_TODOS else [r for r in do_strategy if r.grupo == grupo]
            for k in ks:
                valores = [row.coverage[k] for row in selecionadas if k in row.coverage]
                juntas = [float(row.joined[k]) for row in selecionadas if k in row.joined]
                if not valores:
                    continue
                cells.append(
                    {
                        'strategy': strategy,
                        'grupo': grupo,
                        'k': k,
                        'n': len(valores),
                        'cobertura': bootstrap_ci(valores),
                        'juncao_completa': bootstrap_ci(juntas),
                    }
                )
    return cells
