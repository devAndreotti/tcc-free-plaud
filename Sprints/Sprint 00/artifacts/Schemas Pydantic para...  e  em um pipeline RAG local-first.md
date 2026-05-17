# Schemas Pydantic para `Note`, `Chunk`, `AskResponse` e `ExperimentRun` em um pipeline RAG local-first

Este documento propõe um conjunto de **schemas Pydantic v2** para um sistema **local-first** orientado a **Markdown**, com **citações verificáveis** e **benchmark reproduzível**. A ideia central é manter o contrato de dados pequeno, explícito e auditável. Em um RAG local-first, o arquivo Markdown é a fonte de verdade; os chunks são derivados; as respostas carregam citações estruturadas; e os experimentos registram configuração e métricas suficientes para comparação justa entre execuções.

A proposta abaixo usa validadores de campo e de modelo do Pydantic v2, que são adequados tanto para normalização de entrada quanto para invariantes entre campos [1]. Também usa `Field`, `default_factory` e constraints explícitas para reduzir estados inválidos e tornar os modelos serializáveis e previsíveis [2]. Para benchmark, os campos de `ExperimentRun` foram escolhidos para permitir avaliação de grounding, relevância, fidelidade, atribuição e comportamento de deflexão, dimensões enfatizadas em benchmarks recentes de RAG como **RAGBench** e **GaRAGe** [3] [4].

> **Princípio de desenho:** em um sistema local-first, você deve conseguir abrir um artefato no disco e entender de onde ele veio, qual conteúdo o gerou e como reproduzir o resultado sem depender de estado implícito em banco remoto.

## Visão geral da modelagem

Os quatro modelos principais representam quatro níveis distintos do pipeline. Essa separação é importante porque evita acoplamento excessivo entre ingestão, indexação, inferência e avaliação.

| Modelo | Papel no pipeline | Fonte de verdade | O que precisa responder |
|---|---|---|---|
| `Note` | Documento Markdown canônico | Arquivo local `.md` | Qual nota existe, onde está e qual conteúdo ela contém? |
| `Chunk` | Unidade recuperável e indexável | Derivado da `Note` | Qual trecho foi extraído, de onde veio e em que posição? |
| `AskResponse` | Resposta gerada com grounding | Pergunta + chunks recuperados | O que foi respondido, com quais citações e em quanto tempo? |
| `ExperimentRun` | Execução de benchmark | Configuração + respostas + métricas | Como a execução foi configurada e quão bem performou? |

## Convenções usadas

A implementação abaixo assume três convenções simples. Primeiro, caminhos são armazenados de forma **relativa** para manter portabilidade entre máquinas e diretórios. Segundo, offsets são armazenados em **caracteres**, não em páginas nem em tokens de um tokenizer específico, porque offsets de caractere são mais estáveis para reconstrução e auditoria local. Terceiro, hashes SHA-256 são usados para identificar mudanças de conteúdo e invalidar cache de embeddings ou resultados derivados.

> A documentação do Pydantic recomenda `default_factory` para valores gerados dinamicamente, como ids e timestamps, e destaca que validadores de modelo são o lugar correto para invariantes entre campos [1] [2].

## Implementação sugerida em Pydantic v2

```python
from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SHA256_RE = r"^[a-f0-9]{64}$"
ID_SUFFIX_RE = r"^[a-z]+_[a-f0-9]{32}$"
CITATION_LABEL_RE = r"^C[1-9]\d*$"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class Citation(StrictModel):
    label: str = Field(pattern=CITATION_LABEL_RE, description="Marcador usado no texto, por exemplo C1")
    chunk_id: str = Field(pattern=ID_SUFFIX_RE)
    note_id: str = Field(pattern=ID_SUFFIX_RE)
    note_relative_path: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=600)
    score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("note_relative_path", mode="before")
    @classmethod
    def normalize_note_path(cls, value: str) -> str:
        value = value.replace("\\", "/")
        if value.startswith("/"):
            raise ValueError("note_relative_path deve ser relativo, não absoluto")
        return value

    @model_validator(mode="after")
    def check_span(self) -> "Citation":
        if self.char_end <= self.char_start:
            raise ValueError("char_end deve ser maior que char_start")
        return self


class Note(StrictModel):
    note_id: str = Field(default_factory=lambda: make_id("note"), pattern=ID_SUFFIX_RE)
    relative_path: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=300)
    markdown: str = Field(min_length=1)
    content_sha256: str = Field(default="0" * 64, pattern=SHA256_RE)
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("relative_path", mode="before")
    @classmethod
    def normalize_relative_path(cls, value: str) -> str:
        value = value.replace("\\", "/")
        if value.startswith("/"):
            raise ValueError("relative_path deve ser relativo ao workspace")
        if not value.lower().endswith((".md", ".markdown")):
            raise ValueError("relative_path deve apontar para um arquivo Markdown")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        cleaned = sorted({tag.strip().lower() for tag in value if tag.strip()})
        return cleaned

    @model_validator(mode="after")
    def sync_content_hash(self) -> "Note":
        self.content_sha256 = sha256(self.markdown.encode("utf-8")).hexdigest()
        return self


class Chunk(StrictModel):
    chunk_id: str = Field(default_factory=lambda: make_id("chunk"), pattern=ID_SUFFIX_RE)
    note_id: str = Field(pattern=ID_SUFFIX_RE)
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    token_count: int = Field(gt=0)
    heading_path: tuple[str, ...] = Field(default_factory=tuple)
    text_sha256: str = Field(default="0" * 64, pattern=SHA256_RE)

    @field_validator("heading_path")
    @classmethod
    def clean_heading_path(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(part.strip() for part in value if part.strip())

    @model_validator(mode="after")
    def check_chunk_consistency(self) -> "Chunk":
        if self.char_end <= self.char_start:
            raise ValueError("char_end deve ser maior que char_start")
        self.text_sha256 = sha256(self.text.encode("utf-8")).hexdigest()
        return self


class AskResponse(StrictModel):
    response_id: str = Field(default_factory=lambda: make_id("resp"), pattern=ID_SUFFIX_RE)
    question: str = Field(min_length=1, max_length=2000)
    answer_markdown: str = Field(min_length=1)
    status: Literal["grounded", "insufficient_context", "error"] = "grounded"
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    model_name: str = Field(min_length=1, max_length=200)
    latency_ms: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("retrieved_chunk_ids")
    @classmethod
    def dedupe_retrieved_chunk_ids(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for chunk_id in value:
            if not re.fullmatch(ID_SUFFIX_RE, chunk_id):
                raise ValueError(f"chunk_id inválido: {chunk_id}")
            if chunk_id not in seen:
                seen.add(chunk_id)
                ordered.append(chunk_id)
        return ordered

    @model_validator(mode="after")
    def check_grounding(self) -> "AskResponse":
        if self.status == "grounded" and not self.citations:
            raise ValueError("respostas grounded devem conter ao menos uma citação")

        markers_in_text = set(re.findall(r"\[(C[1-9]\d*)\]", self.answer_markdown))
        markers_in_citations = {c.label for c in self.citations}

        if markers_in_text and markers_in_text != markers_in_citations:
            missing_in_text = markers_in_citations - markers_in_text
            missing_in_citations = markers_in_text - markers_in_citations
            raise ValueError(
                "marcadores de citação inconsistentes; "
                f"sem marcador no texto={sorted(missing_in_text)}, "
                f"sem objeto Citation={sorted(missing_in_citations)}"
            )

        return self


class ExperimentConfig(StrictModel):
    embedder: str = Field(min_length=1)
    retriever: str = Field(min_length=1)
    generator: str = Field(min_length=1)
    search_type: Literal["semantic", "bm25", "hybrid"] = "hybrid"
    top_k: int = Field(gt=0, le=100)
    chunk_size: int = Field(gt=0, le=8000)
    chunk_overlap: int = Field(ge=0, le=4000)
    reranker: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def check_chunk_params(self) -> "ExperimentConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap deve ser menor que chunk_size")
        return self


class ExperimentMetrics(StrictModel):
    answer_relevancy: float | None = Field(default=None, ge=0.0, le=1.0)
    faithfulness: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieval_recall_at_k: float | None = Field(default=None, ge=0.0, le=1.0)
    deflection_tp_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_p50_ms: int | None = Field(default=None, ge=0)


class ExperimentRun(StrictModel):
    run_id: str = Field(default_factory=lambda: make_id("run"), pattern=ID_SUFFIX_RE)
    benchmark_name: str = Field(min_length=1, max_length=200)
    dataset_sha256: str = Field(pattern=SHA256_RE)
    corpus_sha256: str = Field(pattern=SHA256_RE)
    status: Literal["pending", "completed", "failed"] = "pending"
    config: ExperimentConfig
    metrics: ExperimentMetrics = Field(default_factory=ExperimentMetrics)
    response_ids: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    @field_validator("response_ids")
    @classmethod
    def dedupe_response_ids(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for response_id in value:
            if not re.fullmatch(ID_SUFFIX_RE, response_id):
                raise ValueError(f"response_id inválido: {response_id}")
            if response_id not in seen:
                seen.add(response_id)
                ordered.append(response_id)
        return ordered

    @model_validator(mode="after")
    def check_run_state(self) -> "ExperimentRun":
        if self.finished_at and self.finished_at < self.started_at:
            raise ValueError("finished_at não pode ser anterior a started_at")
        if self.status in {"completed", "failed"} and self.finished_at is None:
            raise ValueError("execuções finalizadas precisam de finished_at")
        if self.status == "completed" and not self.response_ids:
            raise ValueError("execução completed deve referenciar pelo menos uma resposta")
        return self
```

## Justificativa de cada campo

A melhor maneira de explicar por que cada campo existe é separar o raciocínio por entidade. Em todas elas, o objetivo é manter apenas o que é necessário para rastreabilidade, reprocessamento e avaliação.

### `Note`

`Note` representa o documento autoritativo. Em um fluxo local-first, ela deve sobreviver mesmo que o índice vetorial seja apagado, porque é dela que todo o resto pode ser reconstruído.

| Campo | Tipo | Validação principal | Justificativa |
|---|---|---|---|
| `note_id` | `str` | pattern `prefix_hex32` | Dá uma identidade estável para joins com `Chunk` e `Citation` sem depender do caminho do arquivo. |
| `relative_path` | `str` | deve ser relativo e terminar em `.md` ou `.markdown` | Mantém portabilidade entre máquinas, evita acoplamento a caminhos absolutos e deixa claro que a fonte é Markdown local. |
| `title` | `str` | `min_length=1` | É o identificador humano da nota, útil para UI, inspeção e debugging. |
| `markdown` | `str` | `min_length=1` | É o conteúdo fonte do sistema; sem ele não há reindexação, renderização nem auditoria. |
| `content_sha256` | `str` | hash SHA-256 recalculado no validador | Permite detectar mudança de conteúdo e invalidar cache de chunking, embedding e respostas antigas. |
| `tags` | `list[str]` | normalização, remoção de vazios e duplicatas | Permite filtros simples sem depender de taxonomia externa. |
| `updated_at` | `datetime` | valor gerado por `default_factory` | Ajuda a ordenar reprocessamento, sincronização e troubleshooting local. |

### `Chunk`

`Chunk` representa a unidade indexável. Ele existe para retrieval, mas também para explicabilidade. Se você não souber exatamente de qual trecho a resposta saiu, você não terá citação confiável.

| Campo | Tipo | Validação principal | Justificativa |
|---|---|---|---|
| `chunk_id` | `str` | pattern `prefix_hex32` | Identidade estável do trecho, usada por retrieval, citações e benchmark. |
| `note_id` | `str` | pattern `prefix_hex32` | Faz o vínculo com a `Note` sem duplicar o documento inteiro. |
| `ordinal` | `int` | `ge=0` | Preserva a ordem original dos chunks dentro da nota. |
| `text` | `str` | `min_length=1` | É o conteúdo efetivamente recuperável pelo retriever e citável na resposta. |
| `char_start` | `int` | `ge=0` | Define o início do span no documento-fonte e permite reconstruir a posição. |
| `char_end` | `int` | `gt=0` e `char_end > char_start` | Fecha o span e evita offsets inválidos. |
| `token_count` | `int` | `gt=0` | Serve para auditoria de chunking e tuning de custo/latência. |
| `heading_path` | `tuple[str, ...]` | limpeza de segmentos vazios | Melhora a legibilidade da origem sem depender apenas de offsets brutos. |
| `text_sha256` | `str` | recalculado a partir de `text` | Permite saber se o conteúdo do chunk mudou mesmo quando o id é mantido ou regenerado. |

### `AskResponse`

`AskResponse` é o artefato mais sensível do pipeline, porque ele representa o que o usuário vê. Por isso, ele precisa guardar não só a resposta, mas também o contexto mínimo de auditabilidade.

| Campo | Tipo | Validação principal | Justificativa |
|---|---|---|---|
| `response_id` | `str` | pattern `prefix_hex32` | Permite persistir e comparar respostas entre execuções. |
| `question` | `str` | `min_length=1` | É a entrada lógica da geração e precisa ser preservada para replay. |
| `answer_markdown` | `str` | `min_length=1` | Markdown é um formato adequado para resposta local-first porque preserva texto, listas, código e referências. |
| `status` | `Literal[...]` | valores controlados | Separa respostas grounded, falta de contexto e erro operacional. |
| `citations` | `list[Citation]` | obrigatório quando `status='grounded'` | Torna o grounding explícito e verificável. |
| `retrieved_chunk_ids` | `list[str]` | ids válidos e sem duplicata | Separa o que foi recuperado do que foi efetivamente citado, útil para análise de retrieval vs. geração. |
| `model_name` | `str` | `min_length=1` | Sem esse campo, comparações entre runs ficam opacas. |
| `latency_ms` | `int` | `ge=0` | Permite medir trade-off entre qualidade e tempo de resposta. |
| `created_at` | `datetime` | valor gerado por `default_factory` | Ajuda em ordenação, replay e histórico. |

### `Citation` como tipo auxiliar indispensável

Embora o pedido central seja sobre os quatro modelos principais, `AskResponse` fica fraco demais sem um tipo auxiliar explícito para citação. Em RAG, **citação não é só um texto decorativo**; ela é uma ligação verificável entre a resposta e um trecho recuperado. Benchmarks recentes mostram que grounding e atribuição a fontes relevantes precisam ser avaliados de forma fina, por passagem, e não apenas por impressão geral da resposta [3] [4].

| Campo | Tipo | Validação principal | Justificativa |
|---|---|---|---|
| `label` | `str` | pattern `C1`, `C2`, ... | Faz o vínculo entre o texto da resposta e o objeto estruturado de citação. |
| `chunk_id` | `str` | pattern válido | Aponta para o chunk efetivamente usado como evidência. |
| `note_id` | `str` | pattern válido | Facilita joins rápidos com a nota fonte. |
| `note_relative_path` | `str` | deve ser relativo | Permite inspeção humana imediata no disco, sem precisar resolver só por id. |
| `char_start` | `int` | `ge=0` | Delimita o início do trecho citado. |
| `char_end` | `int` | `gt=0` e maior que `char_start` | Delimita o final do trecho citado. |
| `quote` | `str` | não vazio, com limite de tamanho | Guarda uma prévia legível da evidência. |
| `score` | `float  None` | entre `0` e `1` | Campo opcional para guardar score de confiança ou ranking. |

### `ExperimentRun`

`ExperimentRun` representa um benchmark executável e reproduzível. A preocupação aqui não é somente medir média de acerto; é registrar **qual corpus**, **qual dataset**, **qual configuração** e **quais saídas** produziram a métrica observada.

| Campo | Tipo | Validação principal | Justificativa |
|---|---|---|---|
| `run_id` | `str` | pattern `prefix_hex32` | Identidade única da execução. |
| `benchmark_name` | `str` | `min_length=1` | Nome legível da suíte, do split ou do cenário de teste. |
| `dataset_sha256` | `str` | hash SHA-256 | Garante que a avaliação referencia exatamente o mesmo conjunto de perguntas e gabaritos. |
| `corpus_sha256` | `str` | hash SHA-256 | Garante que a avaliação foi feita sobre a mesma base documental. |
| `status` | `Literal[...]` | `pending`, `completed` ou `failed` | Explicita o estado da execução e evita leituras ambíguas. |
| `config` | `ExperimentConfig` | validação cruzada em chunking | Guarda o contrato mínimo para reproduzir o pipeline. |
| `metrics` | `ExperimentMetrics` | scores entre `0` e `1` e latência não negativa | Centraliza resultados agregados da execução. |
| `response_ids` | `list[str]` | ids válidos e sem duplicata | Liga a run às respostas produzidas sem embutir todos os objetos. |
| `started_at` | `datetime` | `default_factory` | Marca o início da execução. |
| `finished_at` | `datetime | None` | não pode ser anterior a `started_at` | Fecha a janela temporal da run. |

### `ExperimentConfig` e `ExperimentMetrics` como auxiliares mínimos

Separar configuração e métricas em tipos próprios evita dicionários frouxos e melhora muito a evolução do schema. Além disso, a literatura de avaliação em RAG mostra que olhar apenas uma métrica global quase sempre esconde problemas de grounding, atribuição ou recusa apropriada [3] [4].

| Tipo auxiliar | Campo | Justificativa |
|---|---|---|
| `ExperimentConfig` | `embedder`, `retriever`, `generator` | São os três componentes que mais mudam o comportamento do pipeline. |
| `ExperimentConfig` | `search_type`, `top_k` | Definem o regime de recuperação, fortemente relacionado à qualidade de grounding. |
| `ExperimentConfig` | `chunk_size`, `chunk_overlap` | São parâmetros de indexação que afetam recall, precisão e custo. |
| `ExperimentConfig` | `reranker` | É opcional, mas importante quando existir, porque altera a lista final de evidências. |
| `ExperimentMetrics` | `answer_relevancy` | Mede adequação da resposta à pergunta. |
| `ExperimentMetrics` | `faithfulness` | Mede quão fiel a resposta está ao contexto recuperado. |
| `ExperimentMetrics` | `citation_precision`, `citation_recall` | Medem qualidade da atribuição e do grounding. |
| `ExperimentMetrics` | `retrieval_recall_at_k` | Mede se o retriever trouxe a evidência necessária. |
| `ExperimentMetrics` | `deflection_tp_rate` | Útil quando a resposta correta é não responder por falta de evidência suficiente. |
| `ExperimentMetrics` | `latency_p50_ms` | Resume custo temporal típico da execução. |

## Por que essas validações são as mais importantes

O maior erro em pipelines RAG pequenos é assumir que dados internos não precisam de contrato rígido. Na prática, são exatamente os dados internos que quebram primeiro: caminhos absolutos entram no repositório, offsets ficam inválidos após edição manual, respostas grounded saem sem citação, e benchmark agrega runs incompatíveis. As validações propostas atacam esses pontos onde o sistema costuma falhar em silêncio.

| Tipo de validação | Onde aparece | Por que importa |
|---|---|---|
| Normalização de caminho | `Note.relative_path`, `Citation.note_relative_path` | Evita acoplamento a máquina local e melhora portabilidade. |
| Normalização de listas | `tags`, `retrieved_chunk_ids`, `response_ids` | Remove duplicidade e ruído sem depender da camada de persistência. |
| Invariantes de span | `Chunk`, `Citation` | Impede citações impossíveis e facilita reconstrução exata do trecho. |
| Hash derivado do conteúdo | `Note`, `Chunk` | Torna invalidação de cache previsível. |
| Coerência entre texto e citações | `AskResponse` | Impede que a resposta exiba marcadores sem objeto correspondente, ou o contrário. |
| Coerência de ciclo de vida | `ExperimentRun` | Evita runs finalizadas sem término ou sem saídas vinculadas. |

## Como fazer isso da melhor forma em um sistema real

A melhor implementação para um projeto de TCC ou produto inicial é manter o pipeline dividido em camadas simples. Guarde as notas como arquivos `.md` no repositório. Gere um manifesto em JSONL com as `Note`s. A partir dele, gere outro artefato com `Chunk`s. Salve `AskResponse` por consulta ou sessão. Salve `ExperimentRun` separado, referenciando `response_id`s, em vez de duplicar objetos inteiros. Essa estratégia simplifica versionamento em Git, inspeção manual e replay.

Outra boa prática é tratar `Note` como objeto canônico e todo o resto como derivado. Se uma nota mudar, recalcule `content_sha256`, regenere os `Chunk`s afetados, reinvalide embeddings relacionados e marque respostas antigas como potencialmente obsoletas. O hash torna esse fluxo direto: se o conteúdo mudou, os derivados precisam ser reavaliados. Em sistemas locais, esse desenho é melhor do que confiar em timestamps apenas, porque cópias entre pastas e merges de Git podem embaralhar datas, mas não o conteúdo.

Para citações, prefira sempre **evidência estruturada** em vez de texto livre. Em outras palavras, a resposta pode mostrar algo como `... conforme a nota [C1]`, mas o armazenamento deve manter `chunk_id`, `note_relative_path`, `char_start`, `char_end` e uma `quote` curta. Essa estrutura é o que permite auditoria, navegação para a origem e benchmark de grounding. Benchmarks recentes mostram justamente que modelos podem produzir respostas aparentemente corretas, porém mal atribuídas ou insuficientemente grounded [3] [4].

Para benchmark, não misture métrica agregada com configuração. Uma run só é comparável a outra se você conseguir provar que corpus, dataset e parâmetros eram equivalentes. Por isso `dataset_sha256`, `corpus_sha256` e `config` valem mais do que um simples nome de experimento. Sem esses campos, duas execuções chamadas "baseline" podem, na prática, ser pipelines diferentes.

Também vale a pena manter o estilo do schema conservador. `extra="forbid"` é uma escolha muito boa quando você quer detectar deriva de contrato cedo. Em projetos de pesquisa, campos extras tendem a entrar silenciosamente durante experimentação e depois ficam difíceis de migrar. Com proibição explícita, você descobre o problema no momento em que ele nasce, não meses depois.

## Estrutura de persistência recomendada

Uma organização simples no disco já resolve a maior parte das necessidades de um sistema local-first.

| Caminho | Conteúdo | Observação |
|---|---|---|
| `notes/**/*.md` | documentos Markdown | fonte de verdade humana e versionável |
| `artifacts/notes.jsonl` | serialização de `Note` | manifesto indexável das notas |
| `artifacts/chunks.jsonl` | serialização de `Chunk` | insumo do retriever |
| `artifacts/answers/*.json` | uma `AskResponse` por arquivo | fácil replay e diff |
| `artifacts/runs/*.json` | uma `ExperimentRun` por arquivo | benchmark reproduzível |

## O que eu adicionaria depois, mas não no mínimo viável

No começo, vale resistir à tentação de colocar tudo no schema. Os quatro modelos acima já são suficientes para um pipeline funcional e auditável. Depois que isso estiver estável, as extensões mais úteis costumam ser `schema_version`, `source_app`, `language`, `embedding_model_dim`, `cost`, `trace_id`, `session_id` e `gold_answer` por caso de benchmark. Esses campos são úteis, mas não são estritamente necessários para a primeira versão.

## Conclusão

Se você quiser uma base **enxuta e correta**, use exatamente essa divisão: **`Note` para o documento-fonte, `Chunk` para o trecho recuperável, `AskResponse` para a resposta grounded, e `ExperimentRun` para a execução de benchmark**. O ponto mais importante não é ter muitos campos, mas ter campos que sustentem **reprodução**, **auditoria** e **comparação justa**. Em um RAG local-first, isso vale mais do que qualquer abstração sofisticada.

> Em termos práticos: se um arquivo Markdown mudar hoje, você deve conseguir descobrir quais chunks mudaram, quais respostas ficaram suspeitas e quais benchmarks não são mais comparáveis. Esses schemas foram desenhados justamente para permitir isso.

## Referências

[1]: https://docs.pydantic.dev/latest/concepts/validators/ "Pydantic Validation - Validators"
[2]: https://docs.pydantic.dev/latest/concepts/fields/ "Pydantic Validation - Fields"
[3]: https://arxiv.org/abs/2407.11005 "RAGBench: Explainable Benchmark for Retrieval-Augmented Generation Systems"
[4]: https://aclanthology.org/2025.findings-acl.875/ "GaRAGe: A Benchmark with Grounding Annotations for RAG Evaluation"
