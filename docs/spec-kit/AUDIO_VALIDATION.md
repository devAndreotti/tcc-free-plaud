# Sprint 09 audio validation

Worktree: `wt-audio`; branch: `feat/audio-vad-stt-pipeline`.
Validation date: 2026-09-09. Python 3.12.9, Windows, RTX 2050 4 GB.

## Real execution

- All four executable catalog entries downloaded explicitly from pinned Hugging
  Face revisions and verified by size and SHA-256. GGUF execution is unavailable.
- Silero ONNX ran statefully on CPU. SenseVoiceSmall and Moonshine tiny produced
  English transcripts. Whisper small produced Portuguese transcripts on CPU and
  CUDA; effective device was recorded, rather than inferred from PyTorch.
- A three-second microphone capture produced 47,398 mono PCM16 samples at 16 kHz.
  Stream and worker stopped normally. No speech was detected, so this validates
  recording/flush lifecycle, not microphone speech recognition quality.
- Windows loaded the environment's ONNX Runtime DLL explicitly to avoid an older
  unrelated DLL on PATH. CUDA libraries came from the environment's torch/lib.
  CUDA requires CTranslate2-compatible CUDA 12/cuDNN 9 libraries; installing the
  audio extra alone does not guarantee GPU availability.

## Reproducible fixture evaluation

Six FLEURS WAV fixtures have license, revision, references and hashes in
`pipeline/tests/fixtures/audio/manifest.json`. Portuguese has three recordings of
one sentence; English has three recordings covering two sentences. These samples
prove integration and expose regressions; they do not
establish general STT quality. No private microphone audio is committed.

Mean per-recording metrics from 54 real runs:

| Engine/device | Mode | Samples | WER | CER | Seconds | Real-time factor |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Moonshine CPU | original | 3 | .2206 | .1384 | 2.1462 | .1872 |
| Moonshine CPU | VAD | 3 | .1581 | .1346 | .8743 | .0922 |
| Moonshine CPU | cleaned | 3 | .1581 | .1346 | .5595 | .0657 |
| SenseVoice CPU | original | 3 | .1777 | .1406 | 3.2661 | .3159 |
| SenseVoice CPU | VAD | 3 | .1581 | .1308 | 1.4453 | .1684 |
| SenseVoice CPU | cleaned | 3 | .1581 | .1308 | 1.4959 | .1747 |
| Whisper CPU | original | 6 | .0790 | .0673 | 6.2448 | .7768 |
| Whisper CPU | VAD | 6 | .0895 | .0635 | 5.8517 | .7270 |
| Whisper CPU | cleaned | 6 | .0895 | .0635 | 6.2599 | .7803 |
| Whisper CUDA | original | 6 | .0790 | .0673 | 2.4781 | .3003 |
| Whisper CUDA | VAD | 6 | .0895 | .0635 | 1.0303 | .1285 |
| Whisper CUDA | cleaned | 6 | .0895 | .0635 | .9881 | .1212 |

VAD slightly worsened Whisper WER on this tiny set. Cleaning preserved all
recognized speech in these fixtures; it did not improve WER. Timing includes
loading on the first request, then reuses instances, so cold and warm measurements
are mixed and must not be treated as a controlled performance comparison.
Machine-readable reports remain in ignored `data/results/audio/evaluation-*.json`.

## Automated gates and delivery

Final backend suite on the integrated branch: 432 passed. The 17 VAD tests also
passed through the requested command from the worktree root. Coverage: 89.5%
overall; audio modules reached 91.3% in the preceding report. Ratchet passed
without changing any baseline. Quality Gate doctor: 9/9; script tests: 64/64.
Ruff reports zero errors; all 31 changed Python files pass formatting checks.
Wheel/sdist builds, CLI smoke and audio model/device doctor checks passed.
The real CLI transcribed the Portuguese fixture with `--device auto`, reported
CUDA and persisted native word timestamps. Linux CI installs `libportaudio2`
for sounddevice, as required by its [installation guide](https://python-sounddevice.readthedocs.io/en/latest/installation.html).

UI lint, 12 Vitest tests and build passed. Seven Playwright tests passed against
the isolated Vite server with mocked IPC. Console logs expose a pre-existing
missing `scanVault` mock; these assertions do not prove a full live desktop flow.

The initial high-severity js-yaml audit failure was fixed upstream in main and
integrated without changing UI dependencies in this PR. The repeated audit passed
the high-severity threshold; three moderate Vitest-related findings remain.
Python audit reported no known vulnerabilities. Docker gate is skipped because
this repository has no Docker files.

Delivery and authoritative final CI/SonarCloud status:
[PR #69](https://github.com/devAndreotti/tcc-free-plaud/pull/69).
Copilot reported a review quota limit and did not perform an automated review.
The six required checks must pass on the final head before squash merge.

The first Linux CI run found a missing `libonnxruntime.so`: the lockfile lacked
the separate `sherpa-onnx-core` distribution. The audio extra now pins both Sherpa
packages to 1.13.7. All 12 affected adapter/runtime tests and new real SenseVoice
and Moonshine inference runs passed after installing the native core package.
