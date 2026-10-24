import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from escolio.app.config import Settings
from escolio.benchmark.datasets import load_benchmark_suite
from escolio.benchmark.model_compare import (
    MetadadosExecucao,
    ModeloAlvo,
    RegistroModelo,
    arquivos_da_suite,
    build_models_report,
    comparar_modelos,
    gravar_registros,
    hash_suite,
    parse_modelos,
    slug_modelo,
)
from escolio.benchmark.runners import PIPELINE_VERSION
from escolio.cli import app
from escolio.providers.answer import NO_ANSWER_SENTINEL

runner = CliRunner()
AGORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                slot = sum(ord(char) for char in token) % len(vector)
                vector[slot] += 1.0
            embeddings.append(vector)
        return embeddings


class FakeAnswerProvider:
    """Provider falso: responde o texto dado, ou levanta o erro. Sem rede."""

    provider_name = 'fake'
    temperature = 0.2

    def __init__(self, model: str, *, reply: str = '', error: Exception | None = None) -> None:
        self.model = model
        self.reply = reply
        self.error = error

    def answer(self, question: str, contexts: list[str]) -> str:
        if self.error is not None:
            raise self.error
        return self.reply


def _suite(tmp_path: Path) -> Path:
    documentos = {
        'kafka': '# Kafka\n\nO Apache Kafka foi adotado como broker padrao da plataforma de eventos.\n',
        'redis': '# Redis\n\nO timeout do Redis em staging esta configurado para trinta segundos.\n',
    }
    casos = []
    for nome, texto in documentos.items():
        (tmp_path / f'{nome}.md').write_text(texto, encoding='utf-8')
        (tmp_path / f'{nome}.json').write_text(
            json.dumps({
                'dataset_name': nome,
                'samples': [{'sample_id': f'{nome}-1', 'question': f'Qual a configuracao do {nome}?',
                             'expected_note_id': nome, 'expected_terms': [nome.capitalize()]}],
            }),
            encoding='utf-8',
        )
        casos.append({'case_id': nome, 'document_path': f'{nome}.md', 'dataset_path': f'{nome}.json'})
    (tmp_path / 'negativas.json').write_text(
        json.dumps({'dataset_name': 'negativas', 'samples': [
            {'sample_id': 'neg-1', 'question': 'Qual a receita anual do refeitorio?', 'category': 'negativa'}]}),
        encoding='utf-8',
    )
    caminho = tmp_path / 'suite.json'
    caminho.write_text(
        json.dumps({'suite_name': 'modelos-suite', 'cases': casos, 'negative_dataset_path': 'negativas.json'}),
        encoding='utf-8',
    )
    return caminho


def _executar(tmp_path: Path, modelos: str, fabrica) -> list[RegistroModelo]:
    suite_path = _suite(tmp_path)
    suite = load_benchmark_suite(suite_path)
    return comparar_modelos(
        suite,
        parse_modelos(modelos),
        workspace_dir=tmp_path,
        trabalho_dir=tmp_path / 'trabalho',
        provider_name='fake',
        fabrica=fabrica,
        embedder=FakeEmbedder(),
        suite_hash=hash_suite(arquivos_da_suite(suite_path, suite, tmp_path)),
        executado_em=AGORA,
    )


def _linha_do_modelo(texto: str, modelo: str) -> str:
    return next(linha for linha in texto.splitlines() if linha.startswith(f'| hybrid | Generativo (`{modelo}`)'))


def test_um_modelo_gera_registro_com_metadados_e_relatorio(tmp_path: Path) -> None:
    registros = _executar(
        tmp_path, 'qchat:latest', lambda alvo: FakeAnswerProvider(alvo.modelo, reply=NO_ANSWER_SENTINEL)
    )

    assert len(registros) == 1
    registro = registros[0]
    assert registro.erro is None
    assert registro.comparacao is not None
    assert registro.comparacao.answer_provider == 'fake'
    assert registro.comparacao.answer_model == 'qchat:latest'
    meta = registro.metadados
    assert (meta.nome, meta.tag, meta.provider, meta.temperatura) == ('qchat', 'latest', 'fake', 0.2)
    assert meta.pipeline_version == PIPELINE_VERSION
    assert meta.suite_name == 'modelos-suite'
    assert len(meta.suite_hash) == 64
    assert meta.executado_em == AGORA

    caminhos = gravar_registros(registros, tmp_path / 'saida')
    gravado = RegistroModelo.model_validate_json(caminhos['qchat:latest'].read_text(encoding='utf-8'))
    assert gravado.metadados.modelo == 'qchat:latest'
    assert caminhos['qchat:latest'].name == 'qchat_latest.json'

    texto = build_models_report(registros, comando='python -m escolio benchmark compare-models')
    assert '| `qchat:latest` | qchat | latest | fake | 0,20 | ok | `qchat_latest.json` |' in texto
    assert 'generated_no_answer_sentinel: ' in _linha_do_modelo(texto, 'qchat:latest')


def test_dois_modelos_geram_um_json_cada_e_linhas_separadas_no_relatorio(tmp_path: Path) -> None:
    def fabrica(alvo: ModeloAlvo) -> FakeAnswerProvider:
        if alvo.nome == 'qchat':
            return FakeAnswerProvider(alvo.modelo, reply=NO_ANSWER_SENTINEL)
        return FakeAnswerProvider(alvo.modelo, error=RuntimeError('timeout'))

    registros = _executar(tmp_path, 'qchat:latest,qwen2.5:7b', fabrica)

    assert [r.erro for r in registros] == [None, None]
    assert [r.metadados.modelo for r in registros] == ['qchat:latest', 'qwen2.5:7b']
    caminhos = gravar_registros(registros, tmp_path / 'saida')
    assert sorted(p.name for p in caminhos.values()) == ['qchat_latest.json', 'qwen2.5_7b.json']

    texto = build_models_report(registros)
    assert 'generated_no_answer_sentinel: ' in _linha_do_modelo(texto, 'qchat:latest')
    assert 'provider_error: ' in _linha_do_modelo(texto, 'qwen2.5:7b')
    assert '| `qwen2.5:7b` | qwen2.5 | 7b | fake | 0,20 | ok | `qwen2.5_7b.json` |' in texto


def test_modelo_que_falha_aparece_como_erro_sem_derrubar_os_outros(tmp_path: Path) -> None:
    def fabrica(alvo: ModeloAlvo) -> FakeAnswerProvider:
        if alvo.nome == 'ruim':
            raise ValueError('modelo indisponivel')
        return FakeAnswerProvider(alvo.modelo, reply=NO_ANSWER_SENTINEL)

    registros = _executar(tmp_path, 'ruim:1,bom:1', fabrica)

    ruim, bom = registros
    assert ruim.erro == 'ValueError: modelo indisponivel'
    assert ruim.comparacao is None
    assert ruim.metadados.temperatura is None
    assert bom.erro is None and bom.comparacao is not None

    texto = build_models_report(registros)
    assert '| `ruim:1` | ruim | 1 | fake | — | erro: ValueError: modelo indisponivel | `ruim_1.json` |' in texto
    assert '## Erros' in texto
    assert '- `ruim:1`: ValueError: modelo indisponivel' in texto
    assert 'Generativo (`ruim:1`)' not in texto
    assert 'Generativo (`bom:1`)' in texto


def test_formato_do_markdown_tem_secoes_tabela_e_comando(tmp_path: Path) -> None:
    registros = _executar(tmp_path, 'qchat:latest', lambda alvo: FakeAnswerProvider(alvo.modelo, reply=NO_ANSWER_SENTINEL))
    comando = 'python -m escolio benchmark compare-models --suite s.json --models qchat:latest'

    texto = build_models_report(registros, comando=comando)

    assert texto.startswith('# Comparação de modelos de resposta (IA local)\n')
    assert f'hash SHA-256 `{registros[0].metadados.suite_hash}`' in texto
    assert f'Pipeline `{PIPELINE_VERSION}`' in texto
    assert '\n## Modelos\n' in texto
    assert '| Modelo | Nome | Tag | Provider | Temperatura | Status | JSON |' in texto
    assert '\n## Resultados por estratégia\n' in texto
    assert '| Estratégia | Modo | Positivas respondidas | Accuracy | MRR | Aceitas pela validação | Motivos de descarte | p50 (ms) | p95 (ms) |' in texto
    for estrategia in ('lexical', 'vector', 'hybrid'):
        assert f'| {estrategia} | Generativo (`qchat:latest`) |' in texto
    assert '## Erros' not in texto
    assert texto.endswith(f'## Como reproduzir\n\n```bash\n{comando}\n```\n')


def test_erro_com_barra_vertical_nao_quebra_a_tabela() -> None:
    meta = MetadadosExecucao(
        modelo='x:1', nome='x', tag='1', provider='ollama', temperatura=None, pipeline_version=PIPELINE_VERSION,
        suite_name='s', suite_hash='0' * 64, executado_em=AGORA,
    )
    texto = build_models_report([RegistroModelo(metadados=meta, erro='ValueError: a|b\nlinha 2')])

    assert 'erro: ValueError: a\\|b linha 2' in texto
    assert '## Resultados por estratégia' in texto
    assert '## Como reproduzir' not in texto


def test_parse_modelos_aceita_lista_e_recusa_entrada_invalida() -> None:
    alvos = parse_modelos(' qchat:latest , qwen2.5:7b ,')
    assert [(a.nome, a.tag, a.slug) for a in alvos] == [('qchat', 'latest', 'qchat_latest'), ('qwen2.5', '7b', 'qwen2.5_7b')]
    assert parse_modelos('gpt-local')[0].tag is None

    for ruim in ('', ' , ', 'qchat:latest,qchat:latest', ':7b', 'qwen2.5:7b,qwen2.5_7b'):
        with pytest.raises(ValueError):
            parse_modelos(ruim)


def test_slug_troca_caracteres_que_nao_servem_em_arquivo() -> None:
    assert slug_modelo('qwen2.5:7b') == 'qwen2.5_7b'
    assert slug_modelo('org/modelo:tag v2') == 'org_modelo_tag_v2'


def test_hash_da_suite_muda_com_o_conteudo_e_nao_depende_da_ordem() -> None:
    arquivos = [('suite.json', b'{}'), ('a.md', b'texto a'), ('a.json', b'[]')]
    base = hash_suite(arquivos)

    assert hash_suite(list(reversed(arquivos))) == base
    assert hash_suite([('suite.json', b'{}'), ('a.md', b'texto b'), ('a.json', b'[]')]) != base
    assert hash_suite([('suite.json', b'{}'), ('b.md', b'texto a'), ('a.json', b'[]')]) != base


def test_cli_compare_models_grava_um_json_por_modelo_e_o_relatorio(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='sentence-transformer:fake-hash',
    )
    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda *args, **kwargs: FakeEmbedder())
    monkeypatch.setattr(
        'escolio.benchmark.cli.get_answer_provider',
        lambda name, *, model, **kwargs: FakeAnswerProvider(model, reply=NO_ANSWER_SENTINEL),
    )
    suite_path = _suite(tmp_path)
    saida = tmp_path / 'saida'

    result = runner.invoke(
        app,
        ['benchmark', 'compare-models', '--suite', str(suite_path), '--models', 'qchat:latest,qwen2.5:7b', '--saida-dir', str(saida)],
    )

    assert result.exit_code == 0, result.output
    assert (saida / 'qchat_latest.json').exists() and (saida / 'qwen2.5_7b.json').exists()
    texto = (saida / 'relatorio_modelos.md').read_text(encoding='utf-8')
    assert 'Generativo (`qwen2.5:7b`)' in texto
    assert '--models qchat:latest,qwen2.5:7b' in texto


def test_cli_compare_models_sai_com_erro_quando_todos_falham(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        embedding_model='sentence-transformer:fake-hash',
    )
    monkeypatch.setattr('escolio.benchmark.cli.get_settings', lambda: settings)
    monkeypatch.setattr('escolio.benchmark.cli.get_embedder', lambda *args, **kwargs: FakeEmbedder())

    def sem_provider(name, *, model, **kwargs):
        raise ValueError('sem provider')

    monkeypatch.setattr('escolio.benchmark.cli.get_answer_provider', sem_provider)
    suite_path = _suite(tmp_path)
    saida = tmp_path / 'saida'

    result = runner.invoke(
        app,
        ['benchmark', 'compare-models', '--suite', str(suite_path), '--models', 'qchat:latest', '--saida-dir', str(saida)],
    )

    assert result.exit_code == 1
    assert 'ValueError: sem provider' in (saida / 'relatorio_modelos.md').read_text(encoding='utf-8')


def test_cli_compare_models_recusa_extractive(tmp_path: Path) -> None:
    suite_path = _suite(tmp_path)
    result = runner.invoke(
        app,
        ['benchmark', 'compare-models', '--suite', str(suite_path), '--models', 'qchat:latest',
         '--answer-provider', 'extractive', '--saida-dir', str(tmp_path / 'saida')],
    )
    assert result.exit_code != 0

