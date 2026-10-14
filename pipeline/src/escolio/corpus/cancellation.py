from threading import Event


class CancellationToken:
    """Token cooperativo para interromper operacoes longas entre etapas seguras."""

    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()
