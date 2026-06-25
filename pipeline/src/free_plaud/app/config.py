import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKSPACE_DIR = Path(__file__).resolve().parents[4]
USER_SETTINGS_FILENAME = 'user_settings.json'
USER_SETTING_FIELDS = {
    'embedding_device',
    'embedding_model',
    'retrieval_top_k',
    'default_ask_strategy',
    'default_chunk_size',
    'default_chunk_overlap',
    'corpus_commit_mode',
    'default_corpus_path',
    'corpus_recursive_default',
    'corpus_embedding_batch_size',
    'corpus_index_workers',
    'answer_provider',
    'answer_model',
    'answer_base_url',
    'answer_temperature',
    'answer_timeout_seconds',
}


def _user_settings_path_from_state(state: dict[str, Any]) -> Path:
    workspace_dir = Path(state.get('workspace_dir') or WORKSPACE_DIR)
    results_dir = Path(state.get('results_dir') or workspace_dir / 'data' / 'results')
    return results_dir / USER_SETTINGS_FILENAME


def _read_user_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'user_settings.json precisa conter um objeto JSON: {path}')
    return {key: value for key, value in payload.items() if key in USER_SETTING_FIELDS}


class UserSettingsSource(PydanticBaseSettingsSource):
    """Fonte JSON de preferencias do app, abaixo de env/.env e acima dos defaults."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return _read_user_settings(_user_settings_path_from_state(dict(self.current_state)))


class Settings(BaseSettings):
    """Configuração central do backend local-first."""

    model_config = SettingsConfigDict(
        env_prefix="FREE_PLAUD_",
        env_file=(".env", "pipeline/.env"),
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
    embedding_device: Literal['cpu', 'cuda', 'auto'] = Field(default='cpu')
    answer_provider: Literal['extractive', 'openai-compatible', 'ollama', 'lmstudio'] = Field(default='extractive')
    answer_model: str = Field(default='llama3.1:8b')
    answer_base_url: str | None = Field(default=None)
    answer_api_key: str | None = Field(default=None, exclude=True, repr=False)
    answer_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    answer_timeout_seconds: int = Field(default=60, ge=1, le=300)
    default_ask_strategy: Literal['lexical', 'vector', 'hybrid'] = Field(default='hybrid')
    default_corpus_path: Path | None = Field(default=None)
    corpus_recursive_default: bool = Field(default=True)
    default_chunk_size: int = Field(default=800, ge=100, le=4000)
    default_chunk_overlap: int = Field(default=120, ge=0, le=1000)
    retrieval_top_k: int = Field(default=5, ge=1, le=50)
    corpus_commit_mode: Literal['auto', 'atomic', 'microbatch'] = Field(default='auto')
    corpus_micro_batch_chunks: int = Field(default=64, ge=1, le=2048)
    corpus_micro_batch_files: int = Field(default=32, ge=1, le=512)
    corpus_atomic_max_files: int = Field(default=32, ge=1, le=512)
    corpus_atomic_max_chunks: int = Field(default=64, ge=1, le=2048)
    corpus_embedding_batch_size: int = Field(default=64, ge=1, le=512)
    corpus_upsert_batch_size: int = Field(default=128, ge=1, le=1000)
    corpus_index_workers: int = Field(default=1, ge=1, le=16)

    @model_validator(mode='after')
    def validate_chunk_window(self) -> 'Settings':
        if self.default_chunk_overlap >= self.default_chunk_size:
            raise ValueError('default_chunk_overlap deve ser menor que default_chunk_size')
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            UserSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def user_settings_path_for(settings: Settings | None = None) -> Path:
    resolved = settings or get_settings()
    return resolved.results_dir / USER_SETTINGS_FILENAME


def editable_settings_payload(settings: Settings) -> dict[str, Any]:
    payload = settings.model_dump(mode='json')
    return {key: payload[key] for key in sorted(USER_SETTING_FIELDS)}


def save_user_settings(values: dict[str, Any], *, settings: Settings | None = None) -> Settings:
    base = settings or get_settings()
    path = user_settings_path_for(base)
    current = _read_user_settings(path)
    for key, value in values.items():
        if key not in USER_SETTING_FIELDS:
            raise ValueError(f'Setting nao editavel: {key}')
        if value is None or value == '':
            current.pop(key, None)
        else:
            current[key] = value

    validation_data = base.model_dump()
    validation_data.update(current)
    validated = Settings(**validation_data)

    output = {key: editable_settings_payload(validated)[key] for key in sorted(current)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    get_settings.cache_clear()
    return validated if settings is not None else get_settings()


def reset_user_settings(*, settings: Settings | None = None) -> Settings:
    path = user_settings_path_for(settings)
    if path.exists():
        path.unlink()
    get_settings.cache_clear()
    return get_settings() if settings is None else Settings(**settings.model_dump())
