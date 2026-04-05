from free_plaud.app.config import Settings


def test_settings_have_consistent_defaults() -> None:
    settings = Settings()
    assert settings.default_chunk_size > settings.default_chunk_overlap
    assert settings.retrieval_top_k >= 1


def test_settings_keep_runtime_data_inside_workspace() -> None:
    settings = Settings()

    assert settings.data_dir == settings.workspace_dir / 'data'
    assert settings.notes_dir == settings.workspace_dir / 'data' / 'corpus' / 'notes'
    assert settings.datasets_dir == settings.workspace_dir / 'data' / 'datasets'
    assert settings.results_dir == settings.workspace_dir / 'data' / 'results'
    assert settings.sqlite_path == settings.workspace_dir / 'data' / 'results' / 'free_plaud.sqlite3'
    assert settings.vector_store_dir == settings.workspace_dir / 'data' / 'results' / 'vector_store'
