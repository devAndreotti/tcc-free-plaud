from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração central do backend local-first."""

    model_config = SettingsConfigDict(
        env_prefix="FREE_PLAUD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="dev")
    workspace_dir: Path = Field(default=Path(__file__).resolve().parents[4])
    data_dir: Path = Field(default=Path(__file__).resolve().parents[4] / "data")
    notes_dir: Path = Field(default=Path(__file__).resolve().parents[4] / "data" / "corpus" / "notes")
    datasets_dir: Path = Field(default=Path(__file__).resolve().parents[4] / "data" / "datasets")
    results_dir: Path = Field(default=Path(__file__).resolve().parents[4] / "data" / "results")
    sqlite_path: Path = Field(default=Path(__file__).resolve().parents[4] / "data" / "results" / "free_plaud.sqlite3")
    vector_store_dir: Path = Field(default=Path(__file__).resolve().parents[4] / "data" / "results" / "vector_store")
    vector_collection_name: str = Field(default="free_plaud_chunks")
    embedding_model: str = Field(default="chroma-default")
    default_chunk_size: int = Field(default=800, ge=100, le=4000)
    default_chunk_overlap: int = Field(default=120, ge=0, le=1000)
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    corpus_embedding_batch_size: int = Field(default=64, ge=1, le=512)
    corpus_upsert_batch_size: int = Field(default=128, ge=1, le=1000)
    corpus_index_workers: int = Field(default=1, ge=1, le=16)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
