import sqlite3
from pathlib import Path


def connect_sqlite(path: Path) -> sqlite3.Connection:
    """Abre conexão local com SQLite garantindo o diretório pai."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)
