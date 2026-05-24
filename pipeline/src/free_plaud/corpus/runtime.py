from dataclasses import dataclass
from threading import Lock
from time import perf_counter

from free_plaud.app.config import Settings, get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.providers.embed import Embedder, get_embedder
from free_plaud.storage.vector import LocalVectorStore


@dataclass(frozen=True)
class WarmupResult:
    """Resultado operacional do aquecimento de embeddings no processo atual."""

    model_name: str
    device: str
    elapsed_ms: int
    already_warm: bool


class CorpusRuntime:
    """Cache por processo para recursos caros do corpus.

    A conexao SQLite fica fora do runtime porque o TUI executa operacoes em
    workers diferentes. Reusar embedder e Chroma client ja corta a latencia
    pesada sem cruzar conexao SQLite entre threads.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._lock = Lock()
        self._embedder_key: tuple[str, str] | None = None
        self._embedder: Embedder | None = None
        self._warmed_key: tuple[str, str] | None = None
        self._vector_store_key: tuple[str, str] | None = None
        self._vector_store: LocalVectorStore | None = None

    def _settings_now(self) -> Settings:
        settings = self._settings or get_settings()
        ensure_runtime_dirs(settings)
        return settings

    def get_embedder(self) -> Embedder:
        settings = self._settings_now()
        key = (settings.embedding_model, settings.embedding_device)
        with self._lock:
            if self._embedder is not None and self._embedder_key == key:
                return self._embedder
            self._embedder = get_embedder(settings.embedding_model, device=settings.embedding_device)
            self._embedder_key = key
            self._warmed_key = None
            return self._embedder

    def warmup_embedder(self) -> WarmupResult:
        settings = self._settings_now()
        key = (settings.embedding_model, settings.embedding_device)
        started_at = perf_counter()
        with self._lock:
            if self._embedder is not None and self._embedder_key == key and self._warmed_key == key:
                return WarmupResult(
                    model_name=self._embedder.model_name,
                    device=settings.embedding_device,
                    elapsed_ms=0,
                    already_warm=True,
                )
            if self._embedder is None or self._embedder_key != key:
                self._embedder = get_embedder(settings.embedding_model, device=settings.embedding_device)
                self._embedder_key = key
            if settings.embedding_model.startswith('sentence-transformer:'):
                self._embedder.embed(['free-plaud warmup'])
            self._warmed_key = key
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            return WarmupResult(
                model_name=self._embedder.model_name,
                device=settings.embedding_device,
                elapsed_ms=elapsed_ms,
                already_warm=False,
            )

    def get_vector_store(self) -> LocalVectorStore:
        settings = self._settings_now()
        key = (str(settings.vector_store_dir), settings.vector_collection_name)
        with self._lock:
            if self._vector_store is not None and self._vector_store_key == key:
                return self._vector_store
            self._vector_store = LocalVectorStore(
                settings.vector_store_dir,
                collection_name=settings.vector_collection_name,
            )
            self._vector_store_key = key
            return self._vector_store

    def clear_vector_store(self) -> None:
        with self._lock:
            self._vector_store = None
            self._vector_store_key = None

    def clear(self) -> None:
        with self._lock:
            self._embedder = None
            self._embedder_key = None
            self._warmed_key = None
            self._vector_store = None
            self._vector_store_key = None
