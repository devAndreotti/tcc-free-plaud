# Experimento 23: Velocidade e qualidade da transcrição em CPU

**Data da medição:** 2026-11-02. **Código:** branch `fechamento/transcricao`, a partir de `bd9dfdc` (sherpa-onnx 2.0.1). **O padrão do app não foi alterado.**

## Pergunta e regra de decisão (fixada antes de medir)

O relatório de qualidade registra RTF de 3,60 para `whisper-small` em CPU, contra o limite de 0,80 (RNF-DE-04). RTF é o tempo de transcrição dividido pela duração do áudio. Existe opção com RTF ≤ 0,80 sem piorar demais o erro em português?

Regra: uma opção só é candidata a padrão se tiver RTF ≤ 0,80 em CPU **e** WER no máximo 5 pontos percentuais (pp) acima do `whisper-small` no mesmo áudio.

## Sobre o RTF 3,60

O RTF 3,60 vem do relatório da APS, que **não está no repositório** (`git grep` por "3,60" e "RNF-DE-04" não acha nada). O mais próximo dentro dele é o RTF 0,78 do Whisper em CPU em `docs/spec-kit/AUDIO_VALIDATION.md` (notebook com RTX 2050, 6 gravações curtas do FLEURS, carga do modelo misturada na medição, protocolo diferente). Os dois números não são comparáveis com este experimento.

## Motores que aceitam português

Nenhum motor sherpa do app aceita português.

- `moonshine-tiny-en`: `languages: ["en"]` em `pipeline/src/escolio/providers/models_catalog.json`.
- `sensevoice-small`: `languages: ["zh","en","ja","ko","yue"]` no mesmo arquivo. O `sensevoice-gguf-q8` é `catalog-only` (não executa).
- `AudioRuntime._engine()` (`audio_runtime.py`) levanta `AUDIO_LANGUAGE_UNSUPPORTED` quando o idioma não está em `model.languages`.

Por isso Moonshine e SenseVoice **não foram medidos** com texto em português: seria uma medição sem sentido. Só a família Whisper (faster-whisper) atende português. Não consultei a documentação externa dos modelos, só o catálogo e o código do app.

## Áudio

- Google FLEURS, `pt_br`, split `test`, revisão `70bb2e84b976b7e960aa89f1c648e09c59f894dd` (a mesma do fixture do repositório), licença CC BY 4.0, <https://huggingface.co/datasets/google/fleurs>.
- 40 frases únicas (as primeiras do TSV com 8 palavras ou mais), **541,08 s** de fala, **1.023 palavras** de referência. Referência é a transcrição normalizada do FLEURS, escrita por humanos. Lista em `data/results/experimentos/23_transcricao/manifest_40_frases.json` (pasta ignorada pelo git).
- Limite: textos de notícias/enciclopédia lidos, não fala espontânea de reunião.

## Máquina e método

- Emerald: i5-4690 (4 núcleos), 23 GB, Linux. Python 3.12, faster-whisper 1.2.1, sherpa-onnx 2.0.1. CPU com `CUDA_VISIBLE_DEVICES=""`.
- Caminho do app, com os padrões do app: decode, VAD Silero (ligado por padrão), `WhisperEngine` (beam 5, `int8`, `word_timestamps`, `vad_filter=False`), `clean_segment`. Idioma `pt`.
- Modelos: `Systran/faster-whisper-small` (revisão do catálogo), `-base` e `-tiny` (revisão mais recente, não fixada).
- Por modelo: carga medida à parte; uma inferência de aquecimento de 5 s fora das rodadas; 3 rodadas sobre os 40 arquivos; RTF = tempo (decode + VAD + STT) / duração; mediana das 3 rodadas.
- WER: soma de erros sobre soma de palavras de referência, com `normalized_text` do app (minúsculas, sem pontuação), na última rodada. Números não são normalizados ("19" ≠ "dezenove"). O `jiwer` não está instalado. Pico de memória via `resource.getrusage` (o `/usr/bin/time` não existe no Emerald).
- Script: `data/results/experimentos/23_transcricao/medir_transcricao.py` (cópia no fim deste documento).

## Comandos

```bash
cd ~/tmp/escolio-fech/repo/pipeline
export PYTHONPATH=src HF_HOME=~/tmp/escolio-fech/transcricao/hf
T=~/tmp/escolio-fech/transcricao
CUDA_VISIBLE_DEVICES="" .venv/bin/python $T/medir_transcricao.py \
  $T/models/whisper-small $T/models/silero-vad/onnx/model.onnx \
  $T/audio/manifest.json $T/res2_whisper-small.json --device cpu --rounds 3
# idem para whisper-base e whisper-tiny; --device cuda para a GPU
```

## Resultados (medição final, Emerald ocioso)

Antes da série, o laço esperou a carga de 1 minuto ficar abaixo de 1,0 por 3 leituras seguidas (leituras 15 a 17: 0,96, 0,91, 0,57; `run2.log`). A carga registrada antes de cada modelo inclui a própria medição anterior.

| Modelo | Carga 1 min antes | RTF mediana | Rodadas | WER | Δ WER vs small | Carga do modelo | Pico de memória |
|---|---|---|---|---|---|---|---|
| whisper-small | 0,57 | **0,449** | 0,448 / 0,449 / 0,472 | 5,77% | (base) | 2,29 s | 1.538 MB |
| whisper-base | 4,75 (resíduo da rodada anterior) | **0,170** | 0,170 / 0,172 / 0,168 | 12,12% | +6,35 pp | 0,68 s | 732 MB |
| whisper-tiny | 5,18 (idem) | **0,102** | 0,102 / 0,099 / 0,104 | 19,94% | +14,17 pp | 0,28 s | 613 MB |

Razões em relação à linha de base: `base` é 2,6 vezes mais rápido que `small`; `tiny` é 4,4 vezes.

A primeira série (Emerald com carga 5 a 7 por um Godot headless de outro processo) deu RTF 0,616 / 0,233 / 0,135 e WER 5,77% / 12,12% / 20,33%, com rodadas do `small` variando de 0,72 a 0,51. Está guardada como `res_*.json`, mas **foi descartada por contaminação de carga**. O WER não depende da carga, e só o `tiny` diferiu levemente (20,33% contra 19,94%, provavelmente por não determinismo numérico do int8).

## GPU (referência)

`whisper-small` na GTX 1060 6 GB, sem instalar nada: **falhou**. O `WhisperEngine` pede `compute_type="int8_float16"` em CUDA, e o CTranslate2 respondeu `ValueError: Requested int8_float16 compute type, but the target device or backend do not support efficient int8_float16 computation.` (a GTX 1060 é Pascal). Sem medição de GPU. Achado lateral: esse erro é `ValueError`, e o fallback para CPU do `transcribe()` só captura `RuntimeError`, então, com `audio_device="auto"` e GPU Pascal, o app tende a falhar em vez de cair para CPU. Não foi testado pelo app, só pelo script; vale uma verificação.

**Verificado e corrigido em `a433aeb` (2026-11-03).** No código anterior, `WhisperEngine(..., "auto").transcribe(...)` na GTX 1060 falhou com esse `ValueError`. O `WhisperEngine` passou a pedir o tipo que a placa suporta: `int8_float16` quando existe, como na RTX 2050 do notebook; `int8` na Pascal, que aceita `float32`, `int8` e `int8_float32`; e `float32` se nenhum dos dois existir. Depois da correção, o modelo carrega na GTX 1060, e o erro seguinte é de ambiente: o Emerald não tem `libcublas.so.12`. Com `audio_device="auto"`, esse erro cai no retry e a transcrição termina em CPU, com o aviso "CUDA inference failed; retried once on CPU.". A medição em GPU continua pendente, porque depende das bibliotecas CUDA 12.

## Aplicação da regra de decisão

- `whisper-base`: RTF 0,170 ≤ 0,80, mas WER +6,35 pp (> 5 pp). **Não é candidato.**
- `whisper-tiny`: RTF 0,102 ≤ 0,80, mas WER +14,17 pp. **Não é candidato.**
- Moonshine e SenseVoice: não aceitam português. **Não são candidatos.**
- `whisper-small` (o padrão atual) teve RTF 0,449 no Emerald, abaixo de 0,80.

**Veredito: nenhuma alternativa passa na regra; o padrão `whisper-small` fica.** O `base` erra por pouco no critério de WER (1,35 pp acima do limite), numa amostra pequena; não dá para chamá-lo de descartado com folga.

## Leitura honesta

- O RTF de 0,449 do `small` no Emerald é muito menor que o 3,60 do relatório, apesar de o Emerald ter uma CPU mais antiga que o i5-12450H do notebook. Uma diferença dessa ordem não se explica por CPU. Hipóteses não verificadas: protocolo diferente (carga do modelo ou primeira inferência dentro do tempo), compute type diferente, VAD desligado, notebook em economia de energia ou com outra carga. **Não extrapolo o 0,449 para o notebook.**
- A medição vale como comparação relativa entre os motores (razões acima). O WER de 5,77% do `small` sobre 1.023 palavras é um ponto único, sem intervalo de confiança; 5 pp são cerca de 51 palavras, e a diferença do `base` (6,35 pp) é pequena frente à incerteza de uma amostra dessa escala.
- Texto de leitura limpa em estúdio tende a dar WER menor que fala espontânea.
- O `small` roda com ~1,5 GB de pico, o que pesa em máquinas com pouca memória.

## O que falta confirmar no notebook

1. Repetir o script no i5-12450H com a mesma lista de 40 arquivos, para ver se o RTF do `small` fica ≤ 0,80 ou perto de 3,60, e descobrir de onde vem a diferença.
2. Medir também com VAD desligado e na primeira inferência (a frio), que são os cenários possíveis do relatório da APS.
3. Obter o relatório da APS (ou seu protocolo) para reconciliar o 3,60.
4. Medir o `whisper-small` em GPU na RTX 2050, com `--device cuda`.

## Reprodução no notebook

Em `pipeline/` com `PYTHONPATH=src`, depois de baixar os modelos faster-whisper e o `silero-vad` e montar o manifesto com os mesmos 40 WAV:

```bash
python medir_transcricao.py <MODELO_DIR> <silero/onnx/model.onnx> <manifest.json> <saida.json> --device cpu --rounds 3
```

## Script (`medir_transcricao.py`)

```python
"""Mede RTF e WER de um modelo faster-whisper com o mesmo caminho do app (decode -> VAD Silero -> WhisperEngine -> clean_segment).
Uso (em pipeline/, PYTHONPATH=src):
  python medir_transcricao.py MODELO_DIR SILERO_ONNX MANIFEST.json SAIDA.json [--device cpu|cuda] [--rounds 3]
MANIFEST: {"samples":[{"file":"x.wav","reference":"..."}]}, caminhos relativos ao manifesto."""
import argparse, json, re, resource, statistics, sys
from pathlib import Path
from time import perf_counter
from escolio.benchmark.audio import speech_metrics
from escolio.ingest.audio_cleaner import clean_segment
from escolio.ingest.audio_dsp import decode_audio
from escolio.ingest.audio_vad import SileroVad, SpeechDetector
from escolio.providers.audio_engines import WhisperEngine

a = argparse.ArgumentParser()
a.add_argument("model"); a.add_argument("silero"); a.add_argument("manifest"); a.add_argument("out")
a.add_argument("--device", default="cpu"); a.add_argument("--rounds", type=int, default=3)
a.add_argument("--lang", default="pt")
o = a.parse_args()
man = Path(o.manifest)
samples = json.loads(man.read_text(encoding="utf-8"))["samples"]
eng = WhisperEngine(Path(o.model), o.device)
t = perf_counter(); eng._load(); load_s = perf_counter() - t
# aquecimento fora das rodadas: 1a inferencia aloca buffers
eng.transcribe(decode_audio(man.parent / samples[0]["file"])[:16000 * 5], o.lang)

def run(path):
    t0 = perf_counter()
    audio = decode_audio(path)
    regions = SpeechDetector(SileroVad(Path(o.silero))).process(audio, final=True)
    texts = []
    for r in regions:
        for s in eng.transcribe(audio[r.start_sample:r.end_sample], o.lang):
            texts.append(clean_segment(s).text)
    return perf_counter() - t0, len(audio) / 16000, " ".join(texts)

rounds = []
for _ in range(o.rounds):
    el = dur = 0.0; hyps = []
    for s in samples:
        e, d, h = run(man.parent / s["file"]); el += e; dur += d; hyps.append(h)
    rounds.append({"elapsed": el, "duration": dur, "rtf": el / dur, "hyps": hyps})
# WER agregado (soma de erros / soma de palavras de referencia) sobre a ultima rodada
from escolio.benchmark.audio import edit_distance, normalized_text
err = n = 0
for s, h in zip(samples, rounds[-1]["hyps"]):
    ref = normalized_text(s["reference"]).split(); err += edit_distance(ref, normalized_text(h).split()); n += len(ref)
res = {"model": Path(o.model).name, "device": eng.device, "load_seconds": load_s,
       "audio_seconds": rounds[0]["duration"], "rtf_rounds": [r["rtf"] for r in rounds],
       "rtf_median": statistics.median(r["rtf"] for r in rounds), "wer": err / n, "ref_words": n,
       "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
       "hypotheses": list(zip([s["file"] for s in samples], rounds[-1]["hyps"]))}
Path(o.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print({k: v for k, v in res.items() if k != "hypotheses"})
```
