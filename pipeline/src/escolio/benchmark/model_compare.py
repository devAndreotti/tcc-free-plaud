"""Compara vários modelos de resposta do chat na mesma suíte: um JSON por modelo e um relatório Markdown só.

Cada modelo roda o mesmo fluxo de `benchmark compare` (passada no corpus com o provider do modelo). Um modelo
que falha vira registro com `erro` e não derruba os outros. Funções de parsing, hash e relatório são puras.
"""

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from escolio.benchmark.datasets import BenchmarkSuite
from escolio.benchmark.ia_report import CABECALHO_TABELA, STRATEGIAS, linha_tabela
from escolio.benchmark.runners import (
    PIPELINE_VERSION,
    BenchmarkComparisonResult,
    BenchmarkSettingsSnapshot,
    compare_benchmark_suite,
)
from escolio.providers.answer import AnswerProvider
from escolio.providers.embed import Embedder
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore

NOME_RELATORIO = 'relatorio_modelos.md'


@dataclass(frozen=True)
class ModeloAlvo:
    modelo: str  # como o provider entende, ex.: qchat:latest
    nome: str  # antes do ':', ex.: qchat
    tag: str | None  # depois do ':', ex.: latest; None quando o modelo não tem tag

    @property
    def slug(self) -> str:
        return slug_modelo(self.modelo)


class MetadadosExecucao(BaseModel):
    modelo: str
    nome: str
    tag: str | None
    provider: str
    temperatura: float | None
    pipeline_version: str
    suite_name: str
    suite_hash: str
    executado_em: datetime


class RegistroModelo(BaseModel):
    """Resultado de um modelo: a comparação completa, ou o erro que impediu rodá-la."""

    metadados: MetadadosExecucao
    erro: str | None = None
    comparacao: BenchmarkComparisonResult | None = None


def slug_modelo(modelo: str) -> str:
    """Nome de arquivo seguro para o modelo: 'qwen2.5:7b' vira 'qwen2.5_7b'."""
    return re.sub(r'[^A-Za-z0-9._-]+', '_', modelo).strip('_')


def parse_modelos(texto: str) -> list[ModeloAlvo]:
    """Lê a lista de --models ('qchat:latest,qwen2.5:7b'). Recusa vazio, duplicado e nome sem texto."""
    itens = [item.strip() for item in texto.split(',') if item.strip()]
    if not itens:
        raise ValueError('Informe pelo menos um modelo em --models.')
    alvos: list[ModeloAlvo] = []
    for item in itens:
        nome, _, tag = item.partition(':')
        if not nome.strip():
            raise ValueError(f'Modelo sem nome: {item!r}.')
        alvos.append(ModeloAlvo(modelo=item, nome=nome.strip(), tag=tag.strip() or None))
    if len({alvo.modelo for alvo in alvos}) != len(alvos):
        raise ValueError('Modelo repetido em --models.')
    if len({alvo.slug for alvo in alvos}) != len(alvos):
        raise ValueError('Dois modelos geram o mesmo nome de arquivo.')
    return alvos


def arquivos_da_suite(suite_path: Path, suite: BenchmarkSuite, workspace_dir: Path) -> list[tuple[str, bytes]]:
    """Manifesto, documentos e datasets da suíte, lidos como bytes para o hash."""
    caminhos: list[tuple[str, Path]] = [(suite_path.name, suite_path)]
    for caso in suite.cases:
        caminhos.append((str(caso.document_path), workspace_dir / caso.document_path))
        caminhos.append((str(caso.dataset_path), workspace_dir / caso.dataset_path))
    if suite.negative_dataset_path:
        caminhos.append((str(suite.negative_dataset_path), workspace_dir / suite.negative_dataset_path))
    return [(rotulo, caminho.read_bytes()) for rotulo, caminho in caminhos]


def hash_suite(arquivos: Sequence[tuple[str, bytes]]) -> str:
    """SHA-256 da suíte: muda se o manifesto, um documento ou um dataset mudar. A ordem não importa."""
    digest = hashlib.sha256()
    for rotulo, conteudo in sorted(arquivos):
        digest.update(rotulo.encode('utf-8') + b'\0' + hashlib.sha256(conteudo).digest())
    return digest.hexdigest()


def comparar_modelos(
    suite: BenchmarkSuite,
    alvos: Sequence[ModeloAlvo],
    *,
    workspace_dir: Path,
    trabalho_dir: Path,
    provider_name: str,
    fabrica: Callable[[ModeloAlvo], AnswerProvider],
    embedder: Embedder,
    suite_hash: str,
    top_k: int = 3,
    chunk_size: int = 800,
    overlap: int = 120,
    settings_snapshot: BenchmarkSettingsSnapshot | None = None,
    executado_em: datetime | None = None,
) -> list[RegistroModelo]:
    """Roda o compare uma vez por modelo. Cada modelo usa a própria pasta de SQLite e Chroma em `trabalho_dir`."""
    registros: list[RegistroModelo] = []
    for alvo in alvos:
        provider: AnswerProvider | None = None
        resultado: BenchmarkComparisonResult | None = None
        erro: str | None = None
        inicio = executado_em or datetime.now(UTC)
        try:
            provider = fabrica(alvo)
            pasta = trabalho_dir / alvo.slug
            pasta.mkdir(parents=True, exist_ok=True)
            connection = init_sqlite(pasta / 'benchmark.sqlite3')
            try:
                resultado = compare_benchmark_suite(
                    suite,
                    workspace_dir=workspace_dir,
                    connection=connection,
                    top_k=top_k,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    vector_store=LocalVectorStore(pasta, collection_name='compare_models'),
                    embedder=embedder,
                    settings_snapshot=settings_snapshot,
                    answer_provider=provider,
                )
            finally:
                connection.close()
        except Exception as exc:  # um modelo quebrado registra o erro e os próximos rodam
            erro = f'{type(exc).__name__}: {exc}'
        registros.append(
            RegistroModelo(
                metadados=MetadadosExecucao(
                    modelo=alvo.modelo,
                    nome=alvo.nome,
                    tag=alvo.tag,
                    provider=provider_name,
                    temperatura=getattr(provider, 'temperature', None),
                    pipeline_version=PIPELINE_VERSION,
                    suite_name=suite.suite_name,
                    suite_hash=suite_hash,
                    executado_em=inicio,
                ),
                erro=erro,
                comparacao=resultado,
            )
        )
    return registros


def _celula(texto: str) -> str:
    """Texto seguro dentro de uma célula de tabela Markdown."""
    return texto.replace('|', '\\|').replace('\n', ' ')


def _numero(valor: float | None, casas: int = 2) -> str:
    return '—' if valor is None else f'{valor:.{casas}f}'.replace('.', ',')


def build_models_report(registros: Sequence[RegistroModelo], *, comando: str | None = None) -> str:
    """Relatório Markdown único: metadados por modelo, tabela por estratégia e erros. Só números, sem conclusão."""
    if not registros:
        raise ValueError('Nenhum modelo para o relatório.')
    primeiro = registros[0].metadados
    corpus = next((r.comparacao.corpus for r in registros if r.comparacao and r.comparacao.corpus), None)
    linhas = [
        '# Comparação de modelos de resposta (IA local)',
        '',
        (
            f'Suíte `{primeiro.suite_name}` (hash SHA-256 `{primeiro.suite_hash}`), medida em '
            f'{primeiro.executado_em:%Y-%m-%d %H:%M} (UTC). Pipeline `{primeiro.pipeline_version}`.'
        ),
    ]
    if corpus is not None:
        linhas.append(
            f'Corpus: {corpus.note_count} notas, {corpus.positive_count} perguntas positivas e '
            f'{corpus.negative_count} negativas, profundidade {corpus.retrieval_depth}.'
        )
    linhas += [
        '',
        '## Modelos',
        '',
        '| Modelo | Nome | Tag | Provider | Temperatura | Status | JSON |',
        '|---|---|---|---|---:|---|---|',
    ]
    for registro in registros:
        meta = registro.metadados
        status = 'ok' if registro.erro is None else f'erro: {_celula(registro.erro)}'
        linhas.append(
            f'| `{_celula(meta.modelo)}` | {_celula(meta.nome)} | {_celula(meta.tag or "—")} | {_celula(meta.provider)} '
            f'| {_numero(meta.temperatura, 2)} | {status} | `{slug_modelo(meta.modelo)}.json` |'
        )
    linhas += ['', '## Resultados por estratégia', '', *CABECALHO_TABELA]
    for registro in registros:
        if registro.comparacao is None or registro.comparacao.corpus is None:
            continue
        for estrategia in STRATEGIAS:
            resumo = registro.comparacao.corpus.summaries[estrategia]
            modo = f'Generativo (`{_celula(registro.metadados.modelo)}`)'
            linhas.append(linha_tabela(modo, resumo))
    erros = [r for r in registros if r.erro is not None]
    linhas += [
        '',
        (
            'Positivas respondidas, accuracy e MRR vêm da passada no corpus. Aceitas pela validação = respostas '
            'geradas aceitas / respostas `answer`. Modelos com erro não aparecem na tabela; ver a coluna Status.'
        ),
    ]
    if erros:
        linhas += ['', '## Erros', '']
        linhas += [f'- `{_celula(r.metadados.modelo)}`: {_celula(r.erro or "")}' for r in erros]
    if comando:
        linhas += ['', '## Como reproduzir', '', '```bash', comando, '```']
    return '\n'.join(linhas) + '\n'


def gravar_registros(registros: Sequence[RegistroModelo], saida_dir: Path) -> dict[str, Path]:
    """Grava um JSON por modelo em `saida_dir`; devolve modelo -> caminho."""
    saida_dir.mkdir(parents=True, exist_ok=True)
    caminhos: dict[str, Path] = {}
    for registro in registros:
        caminho = saida_dir / f'{slug_modelo(registro.metadados.modelo)}.json'
        caminho.write_text(registro.model_dump_json(indent=2), encoding='utf-8', newline='\n')
        caminhos[registro.metadados.modelo] = caminho
    return caminhos
