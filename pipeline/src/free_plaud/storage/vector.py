from pathlib import Path


class LocalVectorStore:
    """Placeholder para um store vetorial local.

    A primeira implementação real pode ser ChromaDB, mantendo a interface deste módulo.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def healthcheck(self) -> bool:
        return self.base_dir.exists()
