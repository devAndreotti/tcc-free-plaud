"""Subcomando `benchmark coverage`: cobertura de termos entre trechos, a partir de um JSON do compare.

Lê a passada no corpus (`corpus.queries`), a única com profundidade suficiente para k > 3 e com
notas misturadas, como o chat. Os textos dos trechos vêm das notas da suite, pelos offsets gravados.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from escolio.app.config import get_settings
from escolio.benchmark.coverage import (
    build_coverage_row,
    coverage_summary,
    trechos_do_ranking,
)
from escolio.benchmark.datasets import load_benchmark_dataset, load_benchmark_suite
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document


def _parse_ks(texto: str) -> list[int]:
    try:
        ks = sorted({int(parte) for parte in texto.split(',') if parte.strip()})
    except ValueError:
        raise typer.BadParameter('--k deve ser uma lista de inteiros, ex.: 3,5,10.') from None
    if not ks or ks[0] < 1:
        raise typer.BadParameter('--k deve ter valores de 1 ou mais.')
    return ks


def _termos_e_textos(suite_path: Path, workspace: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    suite = load_benchmark_suite(suite_path)
    textos_por_nota: dict[str, str] = {}
    termos: dict[str, list[str]] = {}
    for case in suite.cases:
        note = structure_document(load_document(workspace / case.document_path))
        # Mesmo texto que chunk_text fatia: normalized_text com strip().
        textos_por_nota[note.note_id] = note.normalized_text.strip()
        for sample in load_benchmark_dataset(workspace / case.dataset_path).samples:
            if sample.category != 'negativa' and sample.expected_terms:
                termos[sample.sample_id] = list(sample.expected_terms)
    return termos, textos_por_nota


def coverage(
    results_path: Path = typer.Option(..., '--results', help="JSON do compare (com a passada no corpus)."),
    suite_path: Path = typer.Option(..., '--suite', '-u', help="Manifesto da suite usada no compare."),
    k: str = typer.Option('3,5,10', '--k', help="Profundidades de corte, separadas por vírgula."),
    saida: Path = typer.Option(..., '--saida', help="Arquivo JSON de saída."),
    workspace: Path | None = typer.Option(
        None, '--workspace', help="Raiz de onde os caminhos da suite são resolvidos (padrão: workspace das settings)."
    ),
) -> None:
    """Cobertura de termos somada entre os k primeiros trechos, por estratégia e grupo de pergunta."""
    ks = _parse_ks(k)
    resultado = json.loads(results_path.read_text(encoding='utf-8'))
    corpus = resultado.get('corpus')
    if not corpus or 'queries' not in corpus:
        typer.echo('O JSON não tem a passada no corpus (corpus.queries). Rode benchmark compare de novo.', err=True)
        raise typer.Exit(code=1)
    profundidade = int(corpus.get('retrieval_depth', 0))
    if ks[-1] > profundidade:
        typer.echo(f'k={ks[-1]} passa da profundidade gravada no compare ({profundidade}).', err=True)
        raise typer.Exit(code=1)

    raiz = workspace or get_settings().workspace_dir
    try:
        termos, textos_por_nota = _termos_e_textos(suite_path, raiz)
        linhas = []
        for estrategia, perguntas in corpus['queries'].items():
            for pergunta in perguntas:
                sample_id = str(pergunta['sample_id'])
                if sample_id not in termos:
                    continue  # negativas e amostras fora da suite
                trechos = trechos_do_ranking(pergunta.get('retrieved', []), textos_por_nota)
                linhas.append(build_coverage_row(estrategia, sample_id, termos[sample_id], trechos, ks))
    except (ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None

    payload = {
        'comparison_id': resultado.get('comparison_id'),
        'suite_name': resultado.get('suite_name'),
        'ks': ks,
        'retrieval_depth': profundidade,
        'perguntas_pontuadas': len({row.sample_id for row in linhas}),
        'celulas': coverage_summary(linhas),
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    typer.echo(json.dumps({'ok': True, 'saida': str(saida), 'perguntas_pontuadas': payload['perguntas_pontuadas']}, indent=2))
