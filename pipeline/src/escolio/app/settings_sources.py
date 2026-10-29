import json
from pathlib import Path
from typing import Any

from pydantic_settings import PydanticBaseSettingsSource

from escolio.app.legacy import legacy_env_values

WORKSPACE_DIR = Path(__file__).resolve().parents[4]
USER_SETTINGS_FILENAME = "user_settings.json"
USER_SETTING_FIELDS = {
    "embedding_device",
    "embedding_model",
    "rerank_model",
    "retrieval_top_k",
    "default_ask_strategy",
    "default_chunk_size",
    "default_chunk_overlap",
    "corpus_commit_mode",
    "default_corpus_path",
    "corpus_recursive_default",
    "corpus_embedding_batch_size",
    "corpus_index_workers",
    "answer_provider",
    "answer_model",
    "answer_base_url",
    "answer_temperature",
    "answer_timeout_seconds",
    "answer_max_tokens",
    "extract_structure",
    "audio_model",
    "audio_language",
    "audio_device",
    "audio_input_device",
}


def _user_settings_path_from_state(state: dict[str, Any]) -> Path:
    workspace_dir = Path(state.get("workspace_dir") or WORKSPACE_DIR)
    results_dir = Path(state.get("results_dir") or workspace_dir / "data" / "results")
    return results_dir / USER_SETTINGS_FILENAME


def _read_user_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"user_settings.json precisa conter um objeto JSON: {path}")
    return {key: value for key, value in payload.items() if key in USER_SETTING_FIELDS}


class UserSettingsSource(PydanticBaseSettingsSource):
    """Fonte JSON de preferencias do app, abaixo de env/.env e acima dos defaults."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return _read_user_settings(
            _user_settings_path_from_state(dict(self.current_state))
        )


class LegacyEnvSource(PydanticBaseSettingsSource):
    """Fallback FREE_PLAUD_* (ambiente e .env), abaixo das variaveis ESCOLIO_*."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        env_file = self.settings_cls.model_config.get("env_file") or ()
        if isinstance(env_file, str):
            env_file = (env_file,)
        return legacy_env_values(self.settings_cls.model_fields.keys(), env_file)
