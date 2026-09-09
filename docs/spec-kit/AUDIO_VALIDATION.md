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
`pipeline/tests/fixtures/audio/manifest.json`. Three recordings per language reuse
one sentence. These samples prove integration and expose regressions; they do not
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

Initial full backend suite: 406 passed, 88.2% coverage; ratchet passed without
changing baselines. After boundary/integration changes: 17 VAD and six integration
tests passed. Quality Gate doctor: 9/9; script tests: 64/64. Final rerun pending.

Known external blocker: UI dependency audit reported high-severity js-yaml
GHSA-2883-xcg3-v3hh and moderate issues. UI dependency changes are outside this
worktree's scope. No merge is permitted until the required security check passes.
PR, CI/SonarCloud babysit and merge evidence will be added after local validation.
