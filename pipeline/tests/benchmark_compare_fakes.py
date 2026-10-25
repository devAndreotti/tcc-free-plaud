"""Provedores falsos e suite pequena para os testes do `benchmark compare`. Sem rede e sem modelos."""

import json
from pathlib import Path

from escolio.app.config import Settings

SUITE_NAME = 'compare-flags-suite'

DOCUMENTO = (
    '# Benchmark\n\n'
    'O benchmark mede recall, latencia e cobertura de citacoes para comparar retrieval.\n\n'
    'A recuperacao vetorial usa embeddings persistidos no ChromaDB local, com dimensao fixa.\n\n'
    'O reranker reordena candidatos com um cross-encoder depois da busca inicial.\n\n'
    'A abstencao do chat aparece quando nenhum trecho sustenta a resposta com seguranca.\n'
)


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


class FakeReranker:
    """Inverte o ranking: o último candidato recebe o maior score. Sem modelo, sem rede."""

    model_name = 'fake-reranker'

    def __init__(self) -> None:
        self.chamadas = 0

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.chamadas += 1
        return [float(indice) for indice in range(len(passages))]


def settings_para(tmp_path: Path) -> Settings:
    return Settings(
        workspace_dir=tmp_path,
        data_dir=tmp_path / 'data',
        notes_dir=tmp_path / 'data' / 'corpus' / 'notes',
        datasets_dir=tmp_path / 'data' / 'datasets',
        results_dir=tmp_path / 'data' / 'results',
        sqlite_path=tmp_path / 'data' / 'results' / 'escolio.sqlite3',
        vector_store_dir=tmp_path / 'data' / 'results' / 'vector_store',
        vector_collection_name='compare_flags',
        embedding_model='sentence-transformer:fake-hash',
    )


def criar_suite(tmp_path: Path) -> Path:
    """Uma nota com quatro parágrafos, perguntas de um trecho e de dois trechos, e uma negativa."""
    (tmp_path / 'benchmark.md').write_text(DOCUMENTO, encoding='utf-8')
    amostras = [
        {'sample_id': 'unica-1', 'question': 'O que o benchmark mede?', 'expected_note_id': 'benchmark',
         'expected_terms': ['recall', 'latencia'], 'category': 'direta'},
        {'sample_id': 'unica-2', 'question': 'Qual o reranker usado?', 'expected_note_id': 'benchmark',
         'expected_terms': ['cross-encoder'], 'category': 'direta'},
        {'sample_id': 'mt-nota-1', 'question': 'Qual banco e o reranker?', 'expected_note_id': 'benchmark',
         'expected_terms': ['ChromaDB', 'cross-encoder'], 'category': 'inferida'},
    ]
    (tmp_path / 'perguntas.json').write_text(
        json.dumps({'dataset_name': 'compare-flags', 'samples': amostras}), encoding='utf-8'
    )
    (tmp_path / 'negativas.json').write_text(
        json.dumps({'dataset_name': 'negativas', 'samples': [
            {'sample_id': 'neg-1', 'question': 'Qual a receita anual do refeitorio?', 'category': 'negativa'}]}),
        encoding='utf-8',
    )
    caminho = tmp_path / 'suite.json'
    caminho.write_text(json.dumps({
        'suite_name': SUITE_NAME,
        'cases': [{'case_id': 'benchmark', 'document_path': 'benchmark.md', 'dataset_path': 'perguntas.json'}],
        'negative_dataset_path': 'negativas.json',
    }), encoding='utf-8')
    return caminho
