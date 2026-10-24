import json
from pathlib import Path

from escolio.benchmark.datasets import load_benchmark_suite
from escolio.benchmark.runners import BenchmarkComparisonResult, compare_benchmark_suite
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[sum(ord(char) for char in token) % len(vector)] += 1.0
            embeddings.append(vector)
        return embeddings


def _suite_com_corpus(tmp_path: Path) -> Path:
    documentos = {
        'kafka': '# Kafka\n\nO Apache Kafka foi adotado como broker padrao da plataforma de eventos.\n',
        'redis': '# Redis\n\nO timeout do Redis em staging esta configurado para trinta segundos.\n',
    }
    casos = []
    for nome, texto in documentos.items():
        (tmp_path / f'{nome}.md').write_text(texto, encoding='utf-8')
        (tmp_path / f'{nome}.json').write_text(
            json.dumps(
                {
                    'dataset_name': nome,
                    'samples': [
                        {
                            'sample_id': f'{nome}-1',
                            'question': f'Qual a configuracao do {nome}?',
                            'expected_note_id': nome,
                            'expected_terms': [nome.capitalize()],
                        }
                    ],
                }
            ),
            encoding='utf-8',
        )
        casos.append({'case_id': nome, 'document_path': f'{nome}.md', 'dataset_path': f'{nome}.json'})
    (tmp_path / 'negativas.json').write_text(
        json.dumps({'dataset_name': 'negativas', 'samples': [{'sample_id': 'neg-1', 'question': 'Qual a receita anual do refeitorio?', 'category': 'negativa'}]}),
        encoding='utf-8',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps({'suite_name': 'faith-suite', 'cases': casos, 'negative_dataset_path': 'negativas.json'}),
        encoding='utf-8',
    )
    return suite_path


def _comparar(tmp_path: Path, nome: str, *, keep_answers: bool) -> BenchmarkComparisonResult:
    pasta = tmp_path / nome
    return compare_benchmark_suite(
        load_benchmark_suite(_suite_com_corpus(tmp_path)),
        workspace_dir=tmp_path,
        connection=init_sqlite(pasta / 'benchmark.sqlite3'),
        top_k=3,
        chunk_size=200,
        overlap=20,
        vector_store=LocalVectorStore(pasta / 'vector_store', collection_name=f'{nome}_compare'),
        embedder=FakeEmbedder(),
        keep_answers=keep_answers,
    )


def test_compare_sem_flag_nao_grava_resposta_nem_contextos(tmp_path: Path) -> None:
    resultado = _comparar(tmp_path, 'sem', keep_answers=False)
    linhas = resultado.corpus.queries['hybrid']
    assert linhas and all(linha.answer is None and linha.contexts is None for linha in linhas)


def test_compare_com_flag_grava_resposta_e_trechos_citados(tmp_path: Path) -> None:
    resultado = _comparar(tmp_path, 'com', keep_answers=True)
    respondidas = [linha for linha in resultado.corpus.queries['hybrid'] if linha.answered]
    assert respondidas, 'a suíte de teste precisa ter perguntas respondidas'
    for linha in respondidas:
        assert linha.answer and linha.answer.strip()
        assert linha.contexts, 'a resposta deve trazer os trechos que ela cita'
        assert all(isinstance(trecho, str) and trecho.strip() for trecho in linha.contexts)
    # Sobrevive ao JSON que o report-ia e o faithfulness leem.
    relido = BenchmarkComparisonResult.model_validate_json(resultado.model_dump_json())
    assert relido.corpus.queries['hybrid'][0].model_dump() == resultado.corpus.queries['hybrid'][0].model_dump()
