"""Comparação em segundo plano: a tela acompanha o progresso e pode cancelar entre uma pergunta e outra."""

from collections import deque
from collections.abc import Callable
from threading import Lock, Thread
from time import monotonic

RECENT_LIMIT = 8
STRATEGY_COUNT = 3


class BenchmarkCancelled(Exception):
    """Levantada pelo callback de progresso para interromper a comparação."""


class BenchmarkJobs:
    """Uma comparação por vez. Fica no processo: sobrevive à troca de tela, não ao fechamento do app.

    `run(on_progress)` faz a comparação e devolve o payload; `total` é o número de passos esperados.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._state: dict | None = None
        self._recent: deque[dict] = deque(maxlen=RECENT_LIMIT)
        self._cancelled = False
        self._started = 0.0

    def start(self, *, suite_name: str, total: int, answer: bool, run: Callable[[Callable], dict]) -> dict:
        with self._lock:
            if self._state and self._state['status'] == 'running':
                return self._snapshot()
            self._cancelled = False
            self._started = monotonic()
            self._recent.clear()
            self._state = {
                'status': 'running',
                'suite_name': suite_name,
                'answer': answer,
                'phase': 'notas',
                'strategy': None,
                'question': None,
                'done': 0,
                'total': max(total, 1),
                'error': None,
                'result': None,
            }
            snapshot = self._snapshot()
        Thread(target=self._work, args=(run,), name='benchmark', daemon=True).start()
        return snapshot

    def _work(self, run: Callable[[Callable], dict]) -> None:
        try:
            result = run(self._on_progress)
        except BenchmarkCancelled:
            self._finish('cancelled')
        except Exception as exc:  # qualquer falha da comparação precisa chegar à tela, não morrer na thread
            self._finish('error', error=str(exc) or exc.__class__.__name__)
        else:
            self._finish('done', result=result)

    def _finish(self, status: str, *, result: dict | None = None, error: str | None = None) -> None:
        with self._lock:
            assert self._state is not None
            self._state.update(status=status, result=result, error=error, question=None)
            self._state['elapsed_ms'] = int((monotonic() - self._started) * 1000)

    def _on_progress(self, event: dict) -> None:
        with self._lock:
            if self._cancelled:
                raise BenchmarkCancelled
            state = self._state
            assert state is not None
            # ponytail: com reranker e linha de base a suite roda duas vezes; `total` já conta as duas passadas.
            state['done'] = min(state['done'] + 1, state['total'])
            state['phase'] = event.get('phase')
            state['strategy'] = event.get('strategy')
            if event.get('phase') == 'corpus':
                state['question'] = event.get('question')
                self._recent.appendleft({
                    'question': event.get('question'),
                    'strategy': event.get('strategy'),
                    'negative': bool(event.get('negative')),
                    'answered': bool(event.get('answered')),
                })

    def _snapshot(self) -> dict:
        assert self._state is not None
        snapshot = dict(self._state)
        snapshot['recent'] = list(self._recent)
        snapshot.setdefault('elapsed_ms', int((monotonic() - self._started) * 1000))
        return snapshot

    def snapshot(self) -> dict | None:
        with self._lock:
            return self._snapshot() if self._state else None

    def cancel(self) -> dict | None:
        with self._lock:
            if self._state and self._state['status'] == 'running':
                self._cancelled = True
            return self._snapshot() if self._state else None


def expected_steps(preview: dict, *, passes: int = 1) -> int:
    """Passos de uma comparação: cada nota em cada estratégia, depois cada pergunta do corpus em cada uma."""
    questions = preview['positive_count'] + preview['negative_count']
    return (preview['note_count'] + questions) * STRATEGY_COUNT * passes
