from chromadb.utils import embedding_functions

from free_plaud.providers.embed import (
    ChromaDefaultEmbedder,
    SentenceTransformerEmbedder,
    get_embedder,
)


def test_get_embedder_resolves_chroma_default() -> None:
    embedder = get_embedder('chroma-default')

    assert isinstance(embedder, ChromaDefaultEmbedder)
    assert embedder.model_name == 'chroma-default'


def test_get_embedder_resolves_sentence_transformer_alias(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSentenceTransformerEmbeddingFunction:
        def __init__(self, *, model_name: str, device: str, normalize_embeddings: bool) -> None:
            captured['model_name'] = model_name
            captured['device'] = device
            captured['normalize_embeddings'] = normalize_embeddings

        def __call__(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 2.0] for _ in texts]

    monkeypatch.setattr(
        embedding_functions,
        'SentenceTransformerEmbeddingFunction',
        FakeSentenceTransformerEmbeddingFunction,
    )

    embedder = get_embedder('sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')

    assert isinstance(embedder, SentenceTransformerEmbedder)
    assert embedder.model_name == 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    assert captured == {
        'model_name': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        'device': 'cpu',
        'normalize_embeddings': False,
    }
    assert embedder.embed(['teste']) == [[1.0, 2.0]]


def test_get_embedder_rejects_unknown_model() -> None:
    try:
        get_embedder('embeddings-que-nao-existem')
    except ValueError as exc:
        assert 'nao suportado' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError para embedding model nao suportado.')
