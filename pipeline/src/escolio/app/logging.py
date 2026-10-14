import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configura logging simples para a fase inicial do projeto."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
