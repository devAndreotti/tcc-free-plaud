# Speech fixtures

Six unmodified test WAV files from Google FLEURS, revision
`70bb2e84b976b7e960aa89f1c648e09c59f894dd`, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Attribution: Google FLEURS contributors, [dataset and references](https://huggingface.co/datasets/google/fleurs).

`manifest.json` fixes source revision, configuration, split, row identifier,
reference text and SHA-256 for every file. The files are the first three
recordings in each Portuguese-Brazil and English-US test TSV, preserving the
original PCM. Portuguese repeats one sentence; English includes two distinct
sentences across the three recordings. This is a
small reproducible integration fixture, not a representative accuracy benchmark.
No microphone recording or private speech is included.

Run from `pipeline` after explicit model provisioning:

```powershell
uv run escolio ingest audio evaluate tests/fixtures/audio/manifest.json --model whisper-small --device cpu
```

The evaluator verifies hashes and compares original audio, VAD and conservative
cleaning. WER/CER use case-folded punctuation-normalized references, without number
normalization. Latency includes per-request validation, decoding and initial model
loading when needed; real-time factor is elapsed seconds divided by audio duration.
