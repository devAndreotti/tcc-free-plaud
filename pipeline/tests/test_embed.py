from chromadb.utils import embedding_functions

from free_plaud.providers.embed import (
    ChromaDefaultEmbedder,
    SentenceTransformerEmbedder,
    describe_embedding_config,
    get_embedder,
)


def test_get_embedder_resolves_chroma_default() -> None:
    embedder = get_embedder('chroma-default', device='cuda')

    assert isinstance(embedder, ChromaDefaultEmbedder)
    assert embedder.model_name == 'chroma-default'

    diagnostics = describe_embedding_config('chroma-default', device='cuda')
    assert diagnostics.device_applicable is False
    assert diagnostics.resolved_device is None
    assert 'nao se aplica' in diagnostics.message


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

    embedder = get_embedder(
        'sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        device='cpu',
    )

    assert isinstance(embedder, SentenceTransformerEmbedder)
    assert embedder.model_name == 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    assert captured == {
        'model_name': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        'device': 'cpu',
        'normalize_embeddings': False,
    }
    assert embedder.embed(['teste']) == [[1.0, 2.0]]


def test_get_embedder_rejects_unavailable_cuda(monkeypatch) -> None:
    monkeypatch.setattr('free_plaud.providers.embed._cuda_available', lambda: False)

    try:
        get_embedder('sentence-transformer:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', device='cuda')
    except ValueError as exc:
        assert 'CUDA indisponivel' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError quando CUDA foi solicitada mas nao esta disponivel.')


def test_get_embedder_auto_uses_cuda_when_available(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSentenceTransformerEmbeddingFunction:
        def __init__(self, *, model_name: str, device: str, normalize_embeddings: bool) -> None:
            captured['device'] = device

        def __call__(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 2.0] for _ in texts]

    monkeypatch.setattr('free_plaud.providers.embed._cuda_available', lambda: True)
    monkeypatch.setattr(
        embedding_functions,
        'SentenceTransformerEmbeddingFunction',
        FakeSentenceTransformerEmbeddingFunction,
    )

    get_embedder('sentence-transformer:modelo-local', device='auto')

    assert captured['device'] == 'cuda'


def test_get_embedder_wraps_sentence_transformer_initialization_errors(monkeypatch) -> None:
    class BrokenSentenceTransformerEmbeddingFunction:
        def __init__(self, *, model_name: str, device: str, normalize_embeddings: bool) -> None:
            _ = (model_name, device, normalize_embeddings)
            raise TypeError("'NoneType' object is not subscriptable")

    monkeypatch.setattr('free_plaud.providers.embed._cuda_available', lambda: True)
    monkeypatch.setattr(
        embedding_functions,
        'SentenceTransformerEmbeddingFunction',
        BrokenSentenceTransformerEmbeddingFunction,
    )

    try:
        get_embedder('sentence-transformer:modelo-local', device='cuda')
    except RuntimeError as exc:
        message = str(exc)
        assert 'Falha ao inicializar embedding sentence-transformer' in message
        assert 'modelo-local' in message
        assert 'cuda' in message
        assert "'NoneType' object is not subscriptable" in message
    else:
        raise AssertionError('Era esperado RuntimeError com diagnostico de inicializacao do sentence-transformer.')


def test_get_embedder_rejects_unknown_model() -> None:
    try:
        get_embedder('embeddings-que-nao-existem')
    except ValueError as exc:
        assert 'nao suportado' in str(exc)
    else:
        raise AssertionError('Era esperado ValueError para embedding model nao suportado.')


def test_chroma_default_single_text_matches_batch_and_reuses_session() -> None:
    import os

    import pytest
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    model_file = os.path.join(ONNXMiniLM_L6_V2.DOWNLOAD_PATH, ONNXMiniLM_L6_V2.EXTRACTED_FOLDER_NAME, 'model.onnx')
    if not os.path.exists(model_file):
        pytest.skip('modelo ONNX do Chroma não baixado nesta máquina')

    embedder = ChromaDefaultEmbedder()
    question = 'Quando foi a reunião do comitê de arquitetura?'
    single = embedder.embed([question])[0]
    batch = embedder.embed([question, 'outro texto qualquer'])[0]

    assert max(abs(a - b) for a, b in zip(single, batch)) < 1e-5
    assert embedder._single_text_function().model is embedder._embedding_function.model
