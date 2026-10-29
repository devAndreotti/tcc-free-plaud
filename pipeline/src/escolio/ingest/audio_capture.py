"""Explicit microphone capture. Callback only copies PCM into a bounded queue."""

import wave
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread

import numpy as np

from escolio.ingest.audio_dsp import AudioResampler
from escolio.ingest.audio_vad import SpeechDetector
from escolio.providers.audio_models import SAMPLE_RATE, AudioError, SpeechRegion


def _default_hostapi_inputs() -> list[tuple[int, dict]]:
    # Só a host API padrão (MME no Windows): o mesmo mic aparece em várias APIs.
    import sounddevice as sd

    hostapi = sd.default.hostapi
    return [
        (index, info)
        for index, info in enumerate(sd.query_devices())
        if info["max_input_channels"] > 0 and info["hostapi"] == hostapi
    ]


def list_input_devices() -> list[str]:
    return [info["name"] for _, info in _default_hostapi_inputs()]


def resolve_input_device(device: int | str | None) -> int | None:
    if device is None or isinstance(device, int):
        return device
    for index, info in _default_hostapi_inputs():
        if info["name"] == device:
            return index
    raise AudioError(
        "AUDIO_DEVICE_UNAVAILABLE",
        f'Microfone "{device}" não encontrado. Conecte-o ou escolha outro em Configurações → Voz.',
    )


class AudioCapture:
    def __init__(
        self,
        path: Path,
        detector: SpeechDetector,
        *,
        device: int | str | None = None,
        queue_size: int = 128,
    ):
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self.path = Path(path)
        self.detector = detector
        self.device = device
        self.queue: Queue = Queue(maxsize=queue_size)
        self.regions: list[SpeechRegion] = []
        self.samples_written = 0
        self.error: str | None = None
        self.error_code: str | None = None
        self._stop = Event()
        self._cancel = Event()
        self._thread: Thread | None = None
        self._stream = None

    def _fail(self, code: str, message: str) -> None:
        self.error_code, self.error = code, message
        self._stop.set()

    def _callback(self, indata, frames, time_info, status) -> None:
        if self._stop.is_set():
            return
        if status:
            self._fail("AUDIO_CAPTURE_OVERFLOW", str(status))
            return
        try:
            self.queue.put_nowait(indata.copy())
        except Full:
            self._fail("AUDIO_CAPTURE_OVERFLOW", "Audio processing queue is full.")

    def start(self) -> None:
        import sounddevice as sd

        if self._thread is not None:
            raise AudioError("AUDIO_CAPTURE_STATE", "Capture instances are single-use.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise AudioError("AUDIO_OUTPUT_EXISTS", "Recording path already exists.")
        try:
            self.device = resolve_input_device(self.device)
            info = sd.query_devices(self.device, kind="input")
            rate = int(info["default_samplerate"])
            sd.check_input_settings(
                device=self.device, channels=1, dtype="float32", samplerate=rate
            )
            self._stream = sd.InputStream(
                device=self.device,
                samplerate=rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._thread = Thread(
                target=self._write, args=(rate,), name="audio-capture", daemon=True
            )
            self._thread.start()
            self._stream.start()
        except Exception as exc:
            self._fail("AUDIO_DEVICE_UNAVAILABLE", str(exc))
            self._close()
            raise AudioError(self.error_code, self.error) from exc

    def _write(self, rate: int) -> None:
        try:
            resampler = AudioResampler(rate)
            with self.path.open("xb") as source, wave.open(source, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                while not self._cancel.is_set():
                    try:
                        block = self.queue.get(timeout=0.05)
                    except Empty:
                        if self._stop.is_set():
                            break
                        continue
                    self._append(output, resampler.process(block))
                if not self._cancel.is_set():
                    self._append(
                        output,
                        resampler.process(np.empty(0, dtype=np.float32), final=True),
                    )
                    self.regions.extend(
                        self.detector.process(np.empty(0, dtype=np.float32), final=True)
                    )
        except Exception as exc:
            self._fail("AUDIO_CAPTURE_FAILED", str(exc))

    def _append(self, output, samples: np.ndarray) -> None:
        output.writeframesraw((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
        self.samples_written += len(samples)
        self.regions.extend(self.detector.process(samples))

    def _close(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception as exc:
                self._fail("AUDIO_DEVICE_UNAVAILABLE", str(exc))
            finally:
                try:
                    self._stream.close()
                except Exception as exc:
                    self._fail("AUDIO_DEVICE_UNAVAILABLE", str(exc))
                finally:
                    self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                self._fail("AUDIO_CAPTURE_TIMEOUT", "Capture worker did not stop.")

    def stop(self) -> Path:
        self._close()
        if self.error:
            raise AudioError(self.error_code or "AUDIO_CAPTURE_FAILED", self.error)
        if self._thread is None:
            raise AudioError("AUDIO_CAPTURE_STATE", "Capture was not started.")
        return self.path

    def cancel(self) -> None:
        self._cancel.set()
        self._close()
