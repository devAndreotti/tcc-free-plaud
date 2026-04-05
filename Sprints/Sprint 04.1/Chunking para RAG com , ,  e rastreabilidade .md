# Chunking para RAG com `chunk_size`, `overlap`, `offsets` e rastreabilidade `note_id -> chunk_id`

**Autor:** Manus AI  
**Data:** 2026-04-04

## Visão geral

Em sistemas de **Retrieval-Augmented Generation (RAG)**, a qualidade da recuperação depende fortemente de como o texto-fonte é segmentado antes da indexação. A literatura prática e experimental converge em um ponto central: **chunks muito grandes tendem a diluir tópicos e reduzir a precisão da recuperação**, enquanto **chunks excessivamente pequenos podem fragmentar sentenças, contexto e evidências** [1] [2]. Além disso, o chunk não deve ser tratado apenas como um bloco de texto; em ambientes profissionais, ele deve ser modelado como uma **unidade rastreável**, com metadados suficientes para reconstruir sua origem, sua posição no texto original e a transformação aplicada durante a ingestão [2] [3].

Este documento apresenta uma forma tecnicamente robusta de implementar chunking para RAG com quatro objetivos simultâneos. O primeiro é preservar **qualidade de recuperação**. O segundo é manter **contexto suficiente** por meio de `chunk_size` e `overlap`. O terceiro é registrar **offsets reproduzíveis** para que cada citação possa ser religada ao texto-fonte. O quarto é manter **lineage** e **provenance**, preservando o vínculo explícito entre `note_id` e `chunk_id` ao longo de todo o pipeline.

## Por que `chunk_size`, `overlap` e offsets precisam ser tratados juntos

A prática mais comum em pipelines RAG é escolher um tamanho fixo ou semiestruturado para cada chunk, seguido por algum grau de sobreposição entre chunks adjacentes. Essa escolha existe porque os trechos recuperados precisam caber no contexto do modelo gerador, e porque modelos de embedding também impõem um limite máximo de entrada [1]. Contudo, o limite máximo técnico não é o mesmo que o tamanho operacional ideal. Um chunk pode caber no modelo e ainda assim ser ruim para recuperação, caso concentre assuntos demais em um único vetor [1].

Os **offsets** entram exatamente nesse ponto. Quando o sistema encontra um trecho relevante, não basta saber qual documento o originou; é necessário saber **onde**, **em qual versão** e **sob qual configuração de segmentação** aquele trecho foi criado. Sem offsets, a citação é frágil. Sem lineage, a reconstrução é frágil. Sem vínculo estável `note_id -> chunk_id`, a recuperação é útil para responder, mas insuficiente para auditar.

A tabela a seguir resume o papel de cada componente na arquitetura.

| Componente | Função principal | Risco se ausente | Recomendação prática |
|---|---|---|---|
| `chunk_size` | Define a quantidade de contexto em cada unidade indexável | Perda de precisão se grande demais; perda de contexto se pequeno demais | Começar com um intervalo operacional moderado e ajustar por avaliação |
| `overlap` | Preserva continuidade semântica entre fronteiras | Perda de evidência em bordas de chunk | Usar sobreposição pequena a moderada, normalmente proporcional ao tamanho do chunk |
| `char_start` / `char_end` | Localizam o trecho no texto-fonte canônico | Citações não reproduzíveis | Registrar offsets absolutos no texto normalizado |
| `note_id` | Identifica a nota ou documento de origem | Ambiguidade de origem | Torná-lo obrigatório em todo chunk |
| `note_version` | Identifica a versão da nota que gerou o chunk | Citações quebradas após edição | Versionar sempre o documento-fonte |
| `chunk_id` | Identifica o chunk de forma estável | Dificuldade para auditoria e cache | Gerar ID determinístico, não aleatório |
| `lineage` | Registra a transformação que levou do documento ao chunk | Impossibilidade de reconstrução | Guardar estratégia, parâmetros e hashes de conteúdo |

## Princípio arquitetural: o chunk é uma evidência, não apenas um texto

A melhor prática em ambientes corporativos e acadêmicos é tratar cada chunk como uma **evidência versionada**. Isso significa que o texto do chunk deve vir acompanhado de um conjunto mínimo de metadados que permita responder, sem ambiguidade, às seguintes perguntas: de qual nota ele veio, qual versão da nota foi usada, quais são seus offsets no texto-fonte, qual foi a estratégia de chunking aplicada, qual foi a configuração de overlap e qual conteúdo exatamente foi embedado.

Essa abordagem é coerente com a literatura recente sobre melhores práticas em RAG, que destaca tanto a importância do **chunking** quanto o valor do enriquecimento com **metadados**, como títulos, palavras-chave e outras âncoras semânticas, para melhorar recuperação e pós-processamento [2]. Em aplicações orientadas à explicabilidade, também é consistente com sistemas que retornam respostas fundamentadas com **source links** e metadados de origem [3].

## Modelo de dados recomendado

A forma mais segura de preservar rastreabilidade é separar o armazenamento em pelo menos duas entidades: a **nota** e o **chunk**. Em sistemas mais maduros, convém introduzir também uma entidade de **versão da nota** e uma tabela de **embeddings** separada, para desacoplar o texto da indexação vetorial.

| Entidade | Chave primária | Papel | Campos essenciais |
|---|---|---|---|
| `notes` | `note_id` | Identidade lógica do documento | `note_id`, `source_type`, `external_ref`, `created_at` |
| `note_versions` | `note_version_id` | Snapshot versionado do conteúdo | `note_version_id`, `note_id`, `version_no`, `content`, `content_sha256`, `normalized_text_sha256`, `created_at` |
| `chunks` | `chunk_id` | Unidade indexável e citável | `chunk_id`, `note_id`, `note_version_id`, `chunk_index`, `char_start`, `char_end`, `text`, `token_count`, `strategy`, `overlap`, `section_path` |
| `chunk_embeddings` | `chunk_embedding_id` | Vetor e configuração de embedding | `chunk_embedding_id`, `chunk_id`, `embedding_model`, `embedding_dim`, `vector_store_doc_id`, `created_at` |
| `retrieval_events` | `retrieval_event_id` | Auditoria de recuperação | `retrieval_event_id`, `query_id`, `chunk_id`, `score`, `rank`, `retriever_version` |

O ponto mais importante desse esquema é que **`chunk_id` não substitui `note_id`; ele o referencia**. Em outras palavras, o vínculo `note_id -> chunk_id` deve ser mantido explicitamente, e não inferido de forma implícita a partir de nomes de arquivo ou chaves derivadas apenas do texto.

## Campos mínimos de proveniência por chunk

Uma implementação profissional normalmente precisa de mais do que o texto do chunk. O quadro abaixo resume um payload mínimo que costuma ser suficiente para reconstrução, auditoria e citações reprodutíveis.

| Campo | Tipo | Finalidade |
|---|---|---|
| `chunk_id` | string | Identificador único e estável do chunk |
| `note_id` | string | Identidade lógica da nota de origem |
| `note_version_id` | string | Versão específica usada na ingestão |
| `chunk_index` | integer | Ordem do chunk dentro da nota |
| `char_start` | integer | Início absoluto no texto normalizado |
| `char_end` | integer | Fim absoluto no texto normalizado |
| `token_start` | integer, opcional | Início em tokens, se o tokenizer for estável |
| `token_end` | integer, opcional | Fim em tokens, se o tokenizer for estável |
| `section_path` | string, opcional | Seção, subtítulo ou hierarquia estrutural |
| `page_start` / `page_end` | integer, opcional | Faixa de páginas para documentos paginados |
| `strategy` | string | Estratégia usada, como `fixed`, `recursive`, `by_title` |
| `chunk_size` | integer | Tamanho-alvo aplicado na geração |
| `overlap` | integer | Sobreposição aplicada |
| `text_sha256` | string | Hash do texto efetivamente embedado |
| `normalization_sha256` | string | Hash do texto normalizado de origem |
| `pipeline_version` | string | Versão do pipeline de ingestão |
| `parent_span_id` | string, opcional | Referência a uma unidade estrutural superior |

## Como gerar `chunk_id` de forma reproduzível

A recomendação central é que o `chunk_id` seja **determinístico**. Em termos práticos, isso significa que, se a mesma versão da nota for submetida ao mesmo pipeline de normalização e à mesma estratégia de chunking, os mesmos chunks deverão receber os mesmos identificadores. Isso facilita cache, deduplicação, auditoria, reindexação e citações persistentes.

Há duas estratégias comuns. A primeira é usar um ID legível baseado em ordenação, como `NOTE-042::v3::c0007`. A segunda é usar um hash derivado dos campos de proveniência, como `sha256(note_id, note_version_id, char_start, char_end, strategy, normalized_text_hash)`. Em produção, é comum combinar as duas formas: um identificador humano-legível para inspeção e um hash técnico para verificação de integridade.

A tabela abaixo compara essas abordagens.

| Estratégia de ID | Exemplo | Vantagem | Limitação |
|---|---|---|---|
| Sequencial legível | `NOTE-042::v3::c0007` | Fácil para depuração e inspeção manual | Pode mudar se a estratégia de chunking mudar |
| Baseado em offsets | `NOTE-042::v3::000120-000340` | Ajuda a localizar o trecho imediatamente | Acoplado à normalização do texto |
| Hash de proveniência | `ch_8f14e45fceea167a` | Estável e bom para auditoria | Menos legível |
| Híbrido | `NOTE-042::v3::c0007::8f14e45f` | Combina legibilidade e robustez | Um pouco mais verboso |

## Estratégias de chunking e quando usar cada uma

Em RAG, a escolha da estratégia deve refletir a estrutura documental. Fontes práticas mostram que **splitting puramente por caracteres** é simples, porém ignora estrutura, podendo cortar sentenças e misturar assuntos; por outro lado, estratégias como **recursive chunking** e **chunking por título/seção** preservam fronteiras mais semânticas e tendem a resultar em melhor recuperação [1].

| Estratégia | Quando usar | Vantagem | Cuidado |
|---|---|---|---|
| Tamanho fixo | Logs, notas simples, dados sem estrutura | Determinística e fácil de reproduzir | Pode cortar frases e argumentos |
| Sliding window com overlap | Textos corridos longos | Reduz perda nas fronteiras | Gera redundância |
| Recursive chunking | Documentação e textos com parágrafos | Preserva melhor a fluidez textual | Precisa de separadores bem definidos |
| Por seção/título | Artigos, normas, documentação técnica | Mantém coerência temática | Pode gerar chunks muito grandes em seções extensas |
| Por elemento estrutural | PDFs parseados em parágrafos, tabelas e blocos | Melhora precisão e explicabilidade | Exige parser confiável |

## Diretrizes operacionais para `chunk_size` e `overlap`

Uma recomendação prática amplamente citada é começar com chunks relativamente pequenos e semânticos. A Unstructured observa que um ponto de partida razoável para experimentação é algo em torno de **250 tokens**, ajustado depois conforme estilo documental e resultados de avaliação [1]. O mesmo material enfatiza que chunks menores e focados tendem a melhorar a precisão da recuperação, enquanto chunks grandes produzem representações mais grosseiras [1].

Em termos de engenharia, a melhor forma de operacionalizar isso é tratar `chunk_size` e `overlap` como **hiperparâmetros avaliáveis**, e não como constantes universais. O quadro abaixo sintetiza um guia inicial.

| Tipo de conteúdo | Estratégia preferida | `chunk_size` inicial | `overlap` inicial | Observação |
|---|---|---:|---:|---|
| Notas de estudo | Recursive ou por parágrafo | 200–350 tokens | 30–60 tokens | Preserva explicações curtas |
| Artigos acadêmicos | Por seção + subchunk | 250–500 tokens | 40–80 tokens | Manter título e subtítulo no metadata |
| Documentação técnica | Por heading/bloco lógico | 200–450 tokens | 32–64 tokens | Não misturar tópicos distintos |
| Atas e transcrições | Por fala ou janela temporal | 120–300 tokens | 20–50 tokens | Adicionar speaker e timestamp |
| PDFs jurídicos/regulatórios | Por artigo/seção | 250–600 tokens | 40–100 tokens | Registrar página e seção |

Esses números não devem ser lidos como valores canônicos. Eles funcionam como **pontos de partida**. O ajuste fino deve ser guiado por avaliação de recuperação, qualidade de resposta, custo de contexto e fidelidade de citação.

## O papel dos offsets: `char_start`, `char_end`, bytes, tokens e páginas

Quando o objetivo inclui **citações reproduzíveis**, offsets deixam de ser opcionais. O mais seguro é manter, pelo menos, **offsets absolutos de caracteres** sobre um texto-fonte canônico e normalizado. Em documentos binários, como PDFs, pode ser útil registrar também **página**, **bloco estrutural** e, quando disponível, **byte offsets** ou coordenadas do parser. Em sistemas centrados em tokenizer estável, também é possível registrar `token_start` e `token_end`, mas isso só é confiável se a versão do tokenizer fizer parte do lineage.

Uma boa regra é distinguir quatro camadas de posição. A primeira é a posição no **texto bruto original**. A segunda é a posição no **texto normalizado** usado para chunking. A terceira é a posição no **chunk gerado**. A quarta é a posição na **representação visual**, como página ou bounding box. O erro mais comum em sistemas apressados é registrar apenas uma dessas camadas e presumir que ela basta para todas as tarefas. Na prática, auditoria robusta quase sempre exige pelo menos a segunda e a quarta.

## Lineage: como documentar a transformação de `note` em `chunk`

No contexto deste problema, **lineage** é o histórico de transformação que conecta a nota original ao chunk indexado. Ele deve permitir responder não apenas *de onde* veio o chunk, mas também *como* ele foi produzido. Isso inclui normalização, limpeza, parser, separadores usados, estratégia de chunking, parâmetros, versão do pipeline e, se necessário, a cadeia de derivação anterior, como `PDF -> OCR -> texto normalizado -> seção -> chunk`.

Uma forma prática de armazenar lineage é por meio de um objeto JSON. O exemplo abaixo é suficiente para a maioria dos casos de uso profissionais.

```json
{
  "chunk_id": "NOTE-042::v3::c0007::8f14e45f",
  "note_id": "NOTE-042",
  "note_version_id": "NOTE-042::v3",
  "chunk_index": 7,
  "strategy": "recursive_by_section",
  "chunk_size": 320,
  "overlap": 48,
  "char_start": 1824,
  "char_end": 2317,
  "section_path": "Resultados > Ablation Study",
  "text_sha256": "1d12a7...",
  "normalization_sha256": "7e9c43...",
  "pipeline_version": "ingest-2026.04",
  "derivation": {
    "source_type": "markdown_note",
    "normalizer": "unicode_nfkc_v2",
    "parser": "markdown_ast_v1",
    "parent_span_id": "NOTE-042::v3::sec-05",
    "embedding_model": "text-embedding-3-large"
  }
}
```

## Exemplo 1: chunking fixo com overlap e offsets absolutos

Considere a seguinte nota canônica, já normalizada, identificada como `note_id = NOTE-001` e `note_version_id = NOTE-001::v1`.

> A recuperação em RAG depende da qualidade do chunking. Chunks muito grandes diluem tópicos diferentes em um único vetor. Chunks muito pequenos podem fragmentar evidências relevantes. Overlap moderado reduz perdas nas fronteiras e offsets absolutos permitem reconstruir a origem exata de cada citação.

Suponha um chunking por caracteres com `chunk_size = 120` e `overlap = 30`. O resultado poderia ser modelado assim.

| `chunk_id` | `note_id` | `chunk_index` | `char_start` | `char_end` | Texto resumido |
|---|---|---:|---:|---:|---|
| `NOTE-001::v1::c0000` | `NOTE-001` | 0 | 0 | 120 | “A recuperação em RAG depende da qualidade do chunking...” |
| `NOTE-001::v1::c0001` | `NOTE-001` | 1 | 90 | 210 | “...Chunks muito grandes diluem tópicos diferentes...” |
| `NOTE-001::v1::c0002` | `NOTE-001` | 2 | 180 | 297 | “...Overlap moderado reduz perdas nas fronteiras...” |

Observe que o segundo chunk começa em `90`, e não em `120`, porque os últimos `30` caracteres do chunk anterior são repetidos. É precisamente essa regra simples que torna o procedimento **reproduzível**. Se o texto-fonte canônico e os parâmetros forem os mesmos, os offsets e os chunks também serão os mesmos.

## Exemplo 2: chunking estrutural para uso acadêmico

Em textos acadêmicos ou relatórios técnicos, a melhor prática geralmente não é cortar em janelas cegas, mas respeitar a estrutura documental. Se uma nota possui seções como **Introdução**, **Metodologia** e **Resultados**, o pipeline pode primeiro extrair `section_path` e só depois aplicar subchunking dentro de cada seção. Dessa forma, evita-se que um chunk una trechos de tópicos distintos, o que prejudica recuperação e interpretabilidade [1].

| `chunk_id` | `note_id` | `section_path` | `char_start` | `char_end` | `strategy` |
|---|---|---|---:|---:|---|
| `ART-014::v2::c0000` | `ART-014` | `Introdução` | 0 | 468 | `by_title_then_recursive` |
| `ART-014::v2::c0001` | `ART-014` | `Metodologia > Dados` | 469 | 913 | `by_title_then_recursive` |
| `ART-014::v2::c0002` | `ART-014` | `Resultados > Ablation` | 914 | 1382 | `by_title_then_recursive` |

Esse padrão é especialmente útil quando a camada de resposta precisa citar evidências como: *“conforme `ART-014::v2::c0002`, seção Resultados > Ablation”*. A citação permanece verificável mesmo após reindexações, desde que a versão da nota e a normalização permaneçam registradas.

## Exemplo 3: formato de citação reproduzível

Uma citação reproduzível em RAG deve apontar para um identificador estável e para a posição do trecho no texto-fonte. Um formato simples e robusto é o seguinte.

| Campo | Exemplo |
|---|---|
| Documento lógico | `note_id = NOTE-001` |
| Versão | `note_version_id = NOTE-001::v1` |
| Chunk | `chunk_id = NOTE-001::v1::c0002` |
| Offset absoluto | `char_start = 180`, `char_end = 297` |
| Localização humana, opcional | `section_path = "Fundamentos > Chunking"` |

A renderização textual da referência pode seguir o padrão abaixo.

> `NOTE-001::v1::c0002` (`char_start=180`, `char_end=297`)

Se o sistema também guardar o texto canônico da versão, uma interface de auditoria consegue destacar exatamente o trecho correspondente, sem necessidade de heurística adicional.

## Exemplo profissional: esquema SQL mínimo

O modelo abaixo implementa o vínculo `note_id -> chunk_id` de forma explícita e auditável.

```sql
create table notes (
  note_id text primary key,
  source_type text not null,
  external_ref text,
  created_at timestamptz not null default now()
);

create table note_versions (
  note_version_id text primary key,
  note_id text not null references notes(note_id),
  version_no integer not null,
  content text not null,
  content_sha256 text not null,
  normalized_text_sha256 text not null,
  created_at timestamptz not null default now(),
  unique (note_id, version_no)
);

create table chunks (
  chunk_id text primary key,
  note_id text not null references notes(note_id),
  note_version_id text not null references note_versions(note_version_id),
  chunk_index integer not null,
  strategy text not null,
  chunk_size integer not null,
  overlap integer not null,
  char_start integer not null,
  char_end integer not null,
  token_count integer,
  section_path text,
  text text not null,
  text_sha256 text not null,
  pipeline_version text not null,
  unique (note_version_id, chunk_index),
  check (char_start >= 0),
  check (char_end > char_start),
  check (overlap >= 0),
  check (chunk_size > overlap)
);

create index idx_chunks_note_id on chunks(note_id);
create index idx_chunks_note_version on chunks(note_version_id);
create index idx_chunks_offsets on chunks(note_version_id, char_start, char_end);
```

Observe que esse desenho preserva três propriedades importantes. Primeiro, ele mantém o relacionamento lógico entre nota e chunk. Segundo, ele ancora o chunk em uma **versão específica** da nota. Terceiro, ele permite que qualquer mecanismo de recuperação ou citação reconstrua o trecho original por offsets.

## Exemplo profissional: implementação em Python

O exemplo abaixo demonstra uma implementação determinística de chunking com offsets absolutos, overlap e geração de `chunk_id` estável. Para manter o exemplo portátil, a contagem de tokens é aproximada por separação em espaços, mas em produção recomenda-se usar o mesmo tokenizer do embedding ou do modelo de recuperação.

```python
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import List


@dataclass
class Chunk:
    chunk_id: str
    note_id: str
    note_version_id: str
    chunk_index: int
    char_start: int
    char_end: int
    chunk_size: int
    overlap: int
    token_count: int
    text: str
    text_sha256: str
    pipeline_version: str


def stable_chunk_id(
    note_id: str,
    note_version_id: str,
    char_start: int,
    char_end: int,
    strategy: str,
    normalized_text_sha256: str,
) -> str:
    raw = f"{note_id}|{note_version_id}|{char_start}|{char_end}|{strategy}|{normalized_text_sha256}"
    digest = sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{note_version_id}::ofs-{char_start:06d}-{char_end:06d}::{digest}"


def chunk_text(
    note_id: str,
    note_version_id: str,
    text: str,
    *,
    chunk_size: int,
    overlap: int,
    strategy: str = "fixed_char_window",
    pipeline_version: str = "ingest-2026.04",
) -> List[Chunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser positivo")
    if overlap < 0:
        raise ValueError("overlap não pode ser negativo")
    if overlap >= chunk_size:
        raise ValueError("overlap deve ser menor que chunk_size")

    normalized_text = " ".join(text.split())
    normalized_text_sha256 = sha256(normalized_text.encode("utf-8")).hexdigest()

    chunks: List[Chunk] = []
    start = 0
    chunk_index = 0

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        chunk_text_value = normalized_text[start:end]
        chunk_id = stable_chunk_id(
            note_id=note_id,
            note_version_id=note_version_id,
            char_start=start,
            char_end=end,
            strategy=strategy,
            normalized_text_sha256=normalized_text_sha256,
        )
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                note_id=note_id,
                note_version_id=note_version_id,
                chunk_index=chunk_index,
                char_start=start,
                char_end=end,
                chunk_size=chunk_size,
                overlap=overlap,
                token_count=len(chunk_text_value.split()),
                text=chunk_text_value,
                text_sha256=sha256(chunk_text_value.encode("utf-8")).hexdigest(),
                pipeline_version=pipeline_version,
            )
        )
        if end == len(normalized_text):
            break
        start = end - overlap
        chunk_index += 1

    return chunks
```

## Exemplo acadêmico: como citar no texto gerado

Em um sistema que retorna respostas com suporte documental, o texto da resposta pode carregar não só a frase de evidência, mas também a referência estruturada. Um formato recomendável é separar a **âncora de evidência** da **renderização textual**. Por exemplo, a aplicação pode armazenar internamente:

```json
{
  "claim": "Chunks menores e semanticamente focados tendem a melhorar a precisão da recuperação.",
  "evidence": [
    {
      "note_id": "ART-014",
      "note_version_id": "ART-014::v2",
      "chunk_id": "ART-014::v2::c0002",
      "char_start": 914,
      "char_end": 1382
    }
  ]
}
```

Na interface, isso pode ser exibido como uma nota de referência. Em um ambiente acadêmico, a renderização pode incluir seção e página; em um ambiente corporativo, pode incluir hyperlink interno para a tela de auditoria do chunk. O ponto crucial é que a **citação precisa apontar para uma evidência persistente**, e não apenas para o texto bruto da resposta.

## Boas práticas de normalização antes do chunking

A rastreabilidade só funciona se o texto-fonte canônico for estável. Por isso, antes de gerar chunks, é recomendável definir uma etapa explícita de **normalização**. Ela deve registrar remoção ou padronização de espaços, forma Unicode, tratamento de quebras de linha, resolução de hífens de final de linha em OCR e, quando necessário, exclusão de cabeçalhos ou rodapés repetidos. Se o texto mostrado ao usuário não for o mesmo texto usado para offsets, a citação deixa de ser confiável.

A tabela abaixo resume um pipeline de normalização seguro.

| Etapa | Exemplo | Impacto na rastreabilidade |
|---|---|---|
| Unicode | NFC ou NFKC | Evita offsets inconsistentes por composição de caracteres |
| Espaços | Colapsar múltiplos espaços | Melhora estabilidade dos offsets |
| Quebras de linha | Padronizar `\n` | Simplifica reconstrução |
| OCR cleanup | Remover hífens artificiais de fim de linha | Evita cortes semânticos falsos |
| Boilerplate removal | Cabeçalhos repetidos | Reduz ruído na recuperação |
| Hash do texto normalizado | `normalized_text_sha256` | Permite verificar integridade |

## O que evitar

Em pipelines de RAG, vários erros parecem pequenos, mas comprometem exatamente a parte que mais importa quando o sistema precisa ser auditável. O primeiro erro é gerar `chunk_id` aleatório a cada ingestão. O segundo é guardar apenas o nome do arquivo, sem `note_version_id`. O terceiro é calcular offsets sobre um texto e exibir outro. O quarto é aplicar overlap sem registrar o valor usado. O quinto é reescrever o texto do chunk, por exemplo com sumarização, e manter os offsets do trecho original como se ainda apontassem para o texto transformado. Nesse último caso, o correto é distinguir **chunk evidencial** de **chunk derivado**, com lineage explícito.

## Padrão recomendado de implementação

Se o objetivo é obter um pipeline confiável para citações reproduzíveis, a melhor estratégia prática é seguir a sequência abaixo. Primeiro, criar uma identidade lógica estável para o documento, representada por `note_id`. Segundo, versionar o conteúdo ingerido em `note_version_id`. Terceiro, normalizar o texto e armazenar seu hash. Quarto, aplicar chunking com parâmetros explícitos de tamanho e overlap. Quinto, gerar `chunk_id` determinístico a partir de offsets e metadados de proveniência. Sexto, indexar embeddings separadamente, sem perder o vínculo com o chunk original. Sétimo, fazer a camada de resposta retornar não só o texto recuperado, mas também a referência estrutural completa.

Esse padrão produz um benefício importante: quando uma resposta precisa ser verificada, o sistema consegue voltar do **texto gerado** para o **chunk recuperado**, do chunk para a **versão da nota**, e da versão para o **documento lógico original**. Em outras palavras, ele preserva uma cadeia auditável de `resposta -> chunk_id -> note_version_id -> note_id`.

## Conclusão

A forma mais sólida de fazer chunking para RAG não consiste apenas em escolher um bom `chunk_size`. Ela exige combinar **segmentação adequada**, **overlap controlado**, **offsets absolutos reproduzíveis** e **lineage explícito**. Em termos práticos, isso significa tratar o chunk como uma evidência versionada, e não como um simples pedaço de texto. Quando essa disciplina é adotada, o sistema ganha em precisão, auditabilidade, reprodutibilidade e confiança.

Para a maioria dos cenários, a recomendação inicial é começar com chunks moderados, orientados por estrutura sempre que possível, adicionar overlap suficiente para reduzir perdas nas bordas e armazenar, para cada chunk, o conjunto mínimo de proveniência: `note_id`, `note_version_id`, `chunk_id`, offsets, estratégia, parâmetros e hashes. Essa combinação é o que transforma um pipeline RAG funcional em um pipeline RAG **citável e auditável**.

## Referências

[1]: https://unstructured.io/blog/chunking-for-rag-best-practices "Unstructured — Chunking Strategies for RAG: Best Practices and Key Methods"
[2]: https://arxiv.org/html/2407.01219v1 "Wang et al. — Searching for Best Practices in Retrieval-Augmented Generation"
[3]: https://isprs-archives.copernicus.org/articles/XLVIII-4-W16-2025/157/2025/ "Santhanavanich and Coors — OGC-AI: A Retrieval-Augmented Large Language Model Interface for Open Geospatial Consortium Web Services"
