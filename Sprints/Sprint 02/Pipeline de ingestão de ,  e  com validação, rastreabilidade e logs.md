# Pipeline de ingestão de `.txt`, `.md` e `.pdf` com validação, rastreabilidade e logs

**Autor:** Manus AI  
**Data:** 2026-04-04

## Resumo

Este documento propõe um desenho de pipeline para ingestão de arquivos `.txt`, `.md` e `.pdf` com **validação de tipo**, **rastreabilidade de `source_path`**, **tratamento estruturado de erro** e **logs claros**, mantendo o processamento **desacoplado da interface de usuário**. A abordagem recomendada modela a ingestão como um serviço de aplicação ou worker independente, acionável por API, fila, agendador ou varredura de diretório, sem conter dependências de componentes visuais. A solução também incorpora princípios de **observabilidade**, **quarentena de falhas** e **proveniência ponta a ponta**, alinhando práticas de engenharia de dados com fundamentos formais de rastreabilidade [1] [2].

Em termos arquiteturais, o pipeline deve tratar cada arquivo recebido como uma **entidade rastreável**, cada estágio como uma **atividade observável** e cada executor técnico como um **agente responsável**, em linha com o modelo conceitual PROV-DM do W3C [2]. Para PDFs, a solução deve distinguir entre documentos com camada textual e documentos digitalizados, adotando validações e rotas de extração apropriadas, já que o formato PDF preserva apresentação visual, e não necessariamente semântica ou ordem de leitura confiável [3].

## 1. Objetivo arquitetural

O objetivo não é apenas “ler arquivos”, mas construir uma **capacidade operacional de ingestão** que permita responder, com precisão, às seguintes perguntas: qual arquivo foi recebido, de onde veio, qual componente o processou, quais validações foram aplicadas, que artefatos intermediários foram gerados, por que uma falha ocorreu e como reprocessar o mesmo item com segurança. Em ambientes profissionais e acadêmicos, essa capacidade é mais valiosa do que uma simples função de parsing, porque viabiliza auditoria, depuração, governança e reprodutibilidade [1] [2].

A principal recomendação é separar a solução em duas camadas. A primeira é a **camada de interação**, que pode ser uma UI, CLI, endpoint REST, serviço de upload, job agendado ou monitor de diretório. A segunda é a **camada de ingestão**, responsável por orquestrar validação, parsing, normalização, persistência e emissão de eventos. A UI apenas solicita o processamento e apresenta o resultado; ela não deve decidir regras de parsing, formatos suportados, estrutura de logs nem políticas de erro.

## 2. Princípios de projeto

A tabela a seguir resume os princípios que tornam o pipeline robusto e desacoplado.

| Princípio | Descrição | Implicação prática |
|---|---|---|
| **Desacoplamento da UI** | A ingestão não depende de componentes visuais nem de ciclo de requisição de interface. | O pipeline pode ser acionado por API, fila, job ou teste automatizado. |
| **Contrato explícito de entrada** | Todo processamento começa a partir de um comando de ingestão bem definido. | O serviço recebe `source_path`, `correlation_id`, `requested_by` e metadados opcionais. |
| **Validação em camadas** | O arquivo é validado em múltiplos níveis, não apenas pela extensão. | Validar existência, acesso, tamanho, assinatura/MIME, capacidade de leitura e qualidade mínima do texto. |
| **Rastreabilidade ponta a ponta** | Cada arquivo, atividade e artefato intermediário deve ser identificável. | Registrar `ingestion_id`, `document_id`, `source_path`, `content_hash`, estágio e timestamps. |
| **Observabilidade estruturada** | Logs devem ser legíveis por humanos e máquinas. | Adotar logs JSON, IDs de correlação e mensagens estáveis por evento. |
| **Falha isolada e recuperável** | Falhas não devem contaminar o restante do sistema. | Encaminhar itens problemáticos para quarentena e permitir reprocessamento. |
| **Idempotência operacional** | Repetir o mesmo comando não deve gerar inconsistência. | Usar hash do conteúdo, chaves de deduplicação e política clara de reingestão. |
| **Evolução controlada** | Novos tipos e validadores devem ser adicionáveis sem refatoração ampla. | Usar registro de parsers, interfaces estáveis e configuração versionada. |

Esses princípios são compatíveis com recomendações de pipelines modernos de ingestão, que enfatizam qualidade na origem, monitoramento, logging robusto e separação entre lógica de extração e infraestrutura do fluxo [1].

## 3. Desenho conceitual do pipeline

O pipeline recomendado pode ser descrito como uma sequência de atividades bem definidas. Primeiro, um **comando de ingestão** entra no sistema. Em seguida, o serviço resolve o arquivo físico, calcula metadados básicos e cria um contexto de rastreabilidade. Depois disso, o sistema executa a **detecção real do tipo**, seleciona o parser adequado, extrai o texto, aplica validações de conteúdo e normaliza a saída para um formato interno canônico. Por fim, persiste os artefatos, registra o resultado, publica eventos de sucesso ou falha e retorna uma resposta para o chamador.

A tabela abaixo organiza o fluxo por responsabilidade.

| Etapa | Entrada | Saída | Objetivo |
|---|---|---|---|
| **Recepção** | Comando de ingestão | Contexto inicial | Receber `source_path` e metadados obrigatórios. |
| **Inspeção física** | Caminho do arquivo | Metadados do arquivo | Validar existência, permissão, tamanho, checksum e tempo de modificação. |
| **Detecção de tipo** | Arquivo bruto | Tipo detectado | Cruzar extensão, MIME e assinatura quando aplicável. |
| **Seleção de parser** | Tipo detectado | Estratégia de parsing | Encaminhar para parser de `.txt`, `.md` ou `.pdf`. |
| **Extração** | Arquivo + parser | Texto bruto + metadados | Produzir conteúdo textual e metadados do parsing. |
| **Validação semântica** | Texto bruto | Resultado de validação | Verificar conteúdo mínimo, legibilidade, limites e coerência. |
| **Normalização** | Texto válido | Documento canônico | Padronizar encoding, quebras de linha, metadados e estrutura interna. |
| **Persistência** | Documento canônico | Artefatos salvos | Armazenar original, texto extraído, manifest e relatório de validação. |
| **Observabilidade** | Eventos do pipeline | Logs e métricas | Tornar o processamento auditável. |
| **Saída operacional** | Resultado do fluxo | Sucesso, falha ou quarentena | Encerrar com estado final claro. |

## 4. Contrato de entrada recomendado

Em vez de passar parâmetros soltos entre funções, recomenda-se um **comando de ingestão** formal. Isso reduz acoplamento e facilita testes, retries e integração entre sistemas.

| Campo | Tipo | Obrigatório | Finalidade |
|---|---|---|---|
| `source_path` | `str` | Sim | Caminho original do arquivo recebido. |
| `declared_media_type` | `str \| None` | Não | Tipo declarado por quem enviou, útil apenas como pista. |
| `requested_by` | `str \| None` | Não | Identifica usuário, serviço ou job chamador. |
| `correlation_id` | `str` | Sim | Correlaciona logs entre sistemas. |
| `received_at` | `datetime` | Sim | Momento lógico de entrada. |
| `source_system` | `str \| None` | Não | Sistema de origem, por exemplo `web-api`, `batch-job`, `cli`. |
| `labels` | `dict[str, str]` | Não | Metadados livres para categorização. |

Esse contrato é melhor do que confiar em dados implícitos da UI, porque elimina dependências de formulário, sessão, rota HTTP ou framework específico.

## 5. Rastreabilidade e proveniência

Um pipeline profissional precisa preservar não apenas o resultado final, mas a **história do processamento**. O modelo PROV-DM do W3C define proveniência como informação sobre **entidades**, **atividades** e **agentes** envolvidos na produção ou transformação de um dado [2]. Essa ideia pode ser aplicada diretamente ao pipeline documental.

> “Provenance is information about entities, activities, and people involved in producing a piece of data or thing, which can be used to form assessments about its quality, reliability or trustworthiness.” — W3C PROV-DM [2]

Na prática, o arquivo original é uma **entidade**. A extração de texto, a validação e a normalização são **atividades**. O serviço de ingestão, a biblioteca de parsing ou o worker executor atuam como **agentes**. O documento final normalizado deriva do arquivo original e dos estágios de processamento intermediários. Esse modelo oferece uma base conceitual forte para auditoria e reprocessamento.

A tabela abaixo traduz o modelo de proveniência para o caso de uso proposto.

| Conceito PROV | Exemplo no pipeline | Campo sugerido |
|---|---|---|
| **Entity** | Arquivo original `relatorio.pdf` | `document_id`, `source_path`, `content_hash` |
| **Entity** | Texto extraído do PDF | `artifact_id`, `artifact_type=text_extracted` |
| **Activity** | Detecção de tipo | `stage=type_detection`, `started_at`, `ended_at` |
| **Activity** | Extração de texto | `stage=parse_pdf`, `parser_version` |
| **Activity** | Validação semântica | `stage=content_validation`, `validation_report_id` |
| **Agent** | Serviço de ingestão | `service_name`, `service_version` |
| **Agent** | Biblioteca PDF | `parser_name`, `parser_version` |
| **Derivation** | Texto normalizado derivado do PDF bruto | `derived_from=document_id` |

Por esse motivo, recomenda-se persistir um **manifesto de ingestão** por item processado. Esse manifesto pode ser um JSON ou registro relacional contendo identificadores, hashes, tempos, estágio final, artefatos gerados, regras aplicadas e eventuais mensagens de erro.

## 6. Validação de tipo e roteamento

A validação de tipo deve evitar o antipadrão de confiar apenas na extensão do arquivo. Um `.pdf` pode estar corrompido, um `.md` pode ser texto puro salvo com extensão incorreta e um `.txt` pode usar encoding incompatível. O pipeline deve combinar pelo menos três sinais: **extensão**, **MIME detectado** e **assinatura do arquivo**, quando houver. Para `.txt` e `.md`, assinatura binária geralmente não existe; nesses casos, a verificação se concentra em legibilidade, encoding e natureza textual. Para `.pdf`, a presença do cabeçalho `%PDF-` é uma verificação útil, embora não suficiente sozinha.

A tabela seguinte propõe uma política de decisão.

| Tipo esperado | Sinais mínimos | Validações adicionais | Resultado se falhar |
|---|---|---|---|
| `.txt` | Extensão textual ou MIME `text/plain` | Detectar encoding, tamanho, taxa de caracteres inválidos | Rejeição ou quarentena |
| `.md` | Extensão `.md` ou MIME textual | Detectar encoding e verificar legibilidade como texto | Rejeição ou tratamento como texto simples, se permitido |
| `.pdf` | Extensão `.pdf`, MIME `application/pdf` e cabeçalho `%PDF-` | Verificar abertura pelo parser, criptografia, presença de páginas e legibilidade do texto extraído | Quarentena, OCR ou rejeição |

Para PDFs, convém distinguir três cenários: documentos textuais, documentos digitalizados e documentos inválidos. A literatura técnica destaca que PDFs preservam aparência, não estrutura semântica confiável, de modo que texto pode vir fragmentado, fora de ordem, em múltiplas colunas ou até ausente, se o arquivo for apenas imagem [3]. Portanto, um pipeline robusto não considera “PDF válido” sinônimo de “PDF útil para extração”.

## 7. Estratégia de parsing por tipo

O pipeline deve selecionar o parser por meio de um registro de estratégias, e não por `if/else` espalhado pela aplicação. Isso melhora extensibilidade e isolamento de responsabilidade.

| Tipo | Estratégia recomendada | Cuidados principais |
|---|---|---|
| `.txt` | Leitura direta como texto | Detectar encoding; rejeitar binário disfarçado de texto. |
| `.md` | Leitura direta como texto | Preservar marcação; normalizar quebras de linha; opcionalmente remover front matter. |
| `.pdf` | Biblioteca especializada, com fallback planejado | Distinguir PDF textual de escaneado; registrar páginas com falha; considerar OCR quando necessário. |

Para `.txt` e `.md`, o parsing costuma ser simples, mas a validação não deve ser negligenciada. Arquivos pequenos demais, vazios, com bytes nulos, com alta incidência de caracteres substitutos ou com encoding inconsistente precisam ser reprovados ou encaminhados para análise. Para `.pdf`, a estratégia deve registrar metadados como número de páginas, presença de criptografia, densidade de texto extraído por página e ocorrência de exceções por página. Isso produz diagnósticos mais úteis do que uma simples mensagem “falha ao extrair PDF”.

## 8. Validação semântica do conteúdo extraído

Depois da extração, ainda é necessário validar se o conteúdo produzido atende ao padrão mínimo de qualidade. Em especial para PDFs, a extração pode tecnicamente “funcionar”, mas resultar em texto quase inútil, com ordem incorreta, blocos vazios ou apenas ruído. Guias recentes de extração de PDF ressaltam a necessidade de escolher a cadeia de ferramentas apropriada, validar a qualidade da saída e executar OCR quando o documento é apenas imagem [3].

Uma abordagem profissional é aplicar um conjunto de validadores semânticos parametrizáveis. A tabela a seguir mostra exemplos relevantes.

| Regra | Tipo aplicável | Exemplo de verificação | Consequência |
|---|---|---|---|
| **Conteúdo não vazio** | Todos | `len(text.strip()) > 0` | Reprovar se vazio |
| **Tamanho mínimo** | Todos | Pelo menos `N` caracteres | Quarentena se abaixo do limiar |
| **Legibilidade textual** | `.txt`, `.md`, `.pdf` | Percentual mínimo de caracteres imprimíveis | Reprovar ou alertar |
| **Densidade por página** | `.pdf` | Texto médio mínimo por página | Acionar OCR ou quarentena |
| **Ausência de bytes nulos** | `.txt`, `.md` | `"\x00" not in content` | Reprovar como texto inválido |
| **Encoding válido** | `.txt`, `.md` | UTF-8 ou conversão segura | Reprovar ou normalizar |
| **Limites operacionais** | Todos | Tamanho máximo, páginas máximas, timeout | Falha controlada |

Além disso, convém registrar **advertências** separadamente de **erros fatais**. Um PDF com 1 página em branco e 19 páginas válidas pode merecer sucesso com aviso, enquanto um PDF inteiro sem camada textual pode ser redirecionado a OCR ou quarentena. Esse desenho evita decisões binárias pobres e melhora a operação.

## 9. Modelo de erro e quarentena

Falhas de ingestão devem ser classificadas e tratadas como primeiro nível de projeto. Em vez de lançar exceções genéricas para a UI, é melhor devolver um **resultado operacional tipado**, com código, categoria, severidade e recomendação de ação. A recomendação contemporânea para pipelines de ingestão é não descartar silenciosamente entradas problemáticas, mas redirecioná-las para um repositório de erro ou quarentena que preserve evidências e permita reprocessamento [1].

A tabela seguinte propõe uma taxonomia útil.

| Categoria | Código | Exemplo | Ação recomendada |
|---|---|---|---|
| **Entrada inválida** | `INPUT_NOT_FOUND` | `source_path` inexistente | Falha imediata |
| **Acesso negado** | `INPUT_PERMISSION_DENIED` | Sem permissão de leitura | Falha imediata |
| **Tipo não suportado** | `UNSUPPORTED_MEDIA_TYPE` | `.docx` enviado em pipeline de `.txt/.md/.pdf` | Falha imediata |
| **Assinatura inconsistente** | `MEDIA_TYPE_MISMATCH` | Extensão `.pdf` sem cabeçalho PDF | Quarentena |
| **Falha de parsing** | `PARSE_ERROR` | Parser não consegue abrir o arquivo | Quarentena |
| **PDF protegido** | `PDF_ENCRYPTED` | Documento com senha | Quarentena ou fluxo manual |
| **Conteúdo insuficiente** | `CONTENT_TOO_POOR` | Texto extraído vazio ou ilegível | OCR, quarentena ou reprovação |
| **Limite operacional** | `PROCESSING_TIMEOUT` | Tempo acima do permitido | Retry ou quarentena |
| **Erro interno** | `INTERNAL_ERROR` | Exceção inesperada | Retry controlado e alerta |

Em qualquer uma dessas situações, o sistema deve registrar **o erro original**, **o estágio onde ocorreu**, **o arquivo afetado**, **o identificador de correlação** e **uma mensagem de diagnóstico estável**, para que alertas e dashboards não dependam de parsing textual frágil.

## 10. Logs claros e estruturados

Logs claros significam duas coisas ao mesmo tempo: uma mensagem compreensível para humanos e um formato rígido para observabilidade automatizada. O padrão mais recomendável é **JSON por evento**, com campos estáveis e baixo acoplamento ao texto livre.

A tabela abaixo apresenta um esquema mínimo de logging.

| Campo | Exemplo | Finalidade |
|---|---|---|
| `timestamp` | `2026-04-04T02:15:11.214Z` | Ordenação temporal |
| `level` | `INFO`, `WARNING`, `ERROR` | Severidade |
| `event` | `ingestion.parse.completed` | Nome estável do evento |
| `message` | `PDF parse completed with warnings` | Leitura humana |
| `correlation_id` | `req-7f2a...` | Correlação entre serviços |
| `ingestion_id` | `ing-20260404-000123` | Identifica a execução de ingestão |
| `document_id` | `doc-a18b...` | Identifica o documento lógico |
| `source_path` | `/dados/entrada/relatorio.pdf` | Rastreabilidade do arquivo |
| `stage` | `parse_pdf` | Estágio do pipeline |
| `status` | `success`, `warning`, `failed` | Resultado do estágio |
| `duration_ms` | `182` | Latência operacional |
| `details` | objeto JSON | Contexto adicional |
| `error_code` | `CONTENT_TOO_POOR` | Código estável de falha |

A seguir, um exemplo de log de sucesso:

```json
{
  "timestamp": "2026-04-04T02:15:11.214Z",
  "level": "INFO",
  "event": "ingestion.validation.completed",
  "message": "Validation completed successfully",
  "correlation_id": "req-85c0a6c8",
  "ingestion_id": "ing-20260404-000123",
  "document_id": "doc-1b74c1d7",
  "source_path": "/dados/entrada/manual.md",
  "stage": "content_validation",
  "status": "success",
  "duration_ms": 14,
  "details": {
    "detected_media_type": "text/markdown",
    "characters": 8421,
    "warnings": []
  }
}
```

Agora, um exemplo de falha em PDF:

```json
{
  "timestamp": "2026-04-04T02:16:44.009Z",
  "level": "ERROR",
  "event": "ingestion.parse.failed",
  "message": "PDF parsing failed because no readable text was extracted",
  "correlation_id": "req-36a9dbe1",
  "ingestion_id": "ing-20260404-000124",
  "document_id": "doc-d3923c7a",
  "source_path": "/dados/entrada/scan.pdf",
  "stage": "parse_pdf",
  "status": "failed",
  "duration_ms": 931,
  "error_code": "CONTENT_TOO_POOR",
  "details": {
    "pages": 18,
    "pages_with_text": 0,
    "parser_name": "pymupdf",
    "suggested_action": "route_to_ocr"
  }
}
```

Esse padrão atende bem tanto análise manual quanto indexação em plataformas de observabilidade.

## 11. Arquitetura desacoplada da UI

Uma implementação limpa pode seguir um estilo de **ports and adapters**, **application service** ou **hexagonal architecture**. Independentemente da escola adotada, o ponto principal é que a UI invoca uma porta estável, como `IngestionService.ingest(command)`, e não conhece detalhes internos de leitura, validação, parser, armazenamento ou logs.

A composição recomendada pode ser descrita da seguinte forma.

| Componente | Papel | Deve conhecer UI? |
|---|---|---|
| **Controller / CLI / Job Trigger** | Recebe solicitação externa e cria comando | Não, exceto sua própria borda |
| **IngestionService** | Orquestra o caso de uso | Não |
| **FileInspector** | Inspeciona arquivo físico e metadados | Não |
| **TypeDetector** | Detecta tipo real | Não |
| **ParserRegistry** | Escolhe parser conforme tipo | Não |
| **DocumentParser** | Extrai texto por tipo | Não |
| **ValidatorChain** | Aplica validações | Não |
| **ArtifactRepository** | Persiste original, texto e relatórios | Não |
| **EventLogger / AuditLogger** | Gera logs e trilha de auditoria | Não |
| **ResultPresenter** | Converte resultado para HTTP, CLI ou UI | Sim, mas apenas na borda |

Esse desenho faz com que a mesma lógica de ingestão seja reutilizável em testes, em execução em lote, em processamento assíncrono e em integração com diferentes front-ends.

## 12. Exemplo profissional em Python

A seguir está um exemplo de arquitetura em Python orientada a interfaces. O objetivo não é fornecer um framework completo, mas mostrar a separação correta de responsabilidades.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Any
import hashlib
import json
import mimetypes


@dataclass(frozen=True)
class IngestionCommand:
    source_path: str
    correlation_id: str
    received_at: datetime
    requested_by: str | None = None
    declared_media_type: str | None = None
    source_system: str | None = None
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FileMetadata:
    source_path: str
    size_bytes: int
    sha256: str
    extension: str
    mime_type: str | None
    modified_at: datetime


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    source_path: str
    detected_type: str
    text: str
    metadata: dict[str, Any]
    warnings: list[str]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue]


@dataclass(frozen=True)
class IngestionResult:
    status: str
    ingestion_id: str
    document_id: str | None
    source_path: str
    detected_type: str | None
    error_code: str | None = None
    message: str | None = None
    warnings: list[str] = field(default_factory=list)


class DocumentParser(Protocol):
    supported_types: tuple[str, ...]

    def parse(self, file_path: Path, metadata: FileMetadata) -> ParsedDocument:
        ...


class Logger(Protocol):
    def info(self, event: str, **payload: Any) -> None:
        ...

    def warning(self, event: str, **payload: Any) -> None:
        ...

    def error(self, event: str, **payload: Any) -> None:
        ...


class JsonLogger:
    def _emit(self, level: str, event: str, **payload: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event,
            **payload,
        }
        print(json.dumps(record, ensure_ascii=False))

    def info(self, event: str, **payload: Any) -> None:
        self._emit("INFO", event, **payload)

    def warning(self, event: str, **payload: Any) -> None:
        self._emit("WARNING", event, **payload)

    def error(self, event: str, **payload: Any) -> None:
        self._emit("ERROR", event, **payload)


class FileInspector:
    def inspect(self, source_path: str) -> FileMetadata:
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(source_path)
        if not path.is_file():
            raise ValueError("source_path does not point to a file")

        data = path.read_bytes()
        stat = path.stat()
        mime_type, _ = mimetypes.guess_type(path.name)
        return FileMetadata(
            source_path=str(path),
            size_bytes=stat.st_size,
            sha256=hashlib.sha256(data).hexdigest(),
            extension=path.suffix.lower(),
            mime_type=mime_type,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )


class TypeDetector:
    def detect(self, metadata: FileMetadata, first_bytes: bytes) -> str:
        if metadata.extension == ".pdf" and first_bytes.startswith(b"%PDF-"):
            return "application/pdf"
        if metadata.extension == ".md":
            return "text/markdown"
        if metadata.extension == ".txt":
            return "text/plain"
        raise ValueError("UNSUPPORTED_MEDIA_TYPE")


class TxtParser:
    supported_types = ("text/plain",)

    def parse(self, file_path: Path, metadata: FileMetadata) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8")
        return ParsedDocument(
            document_id=metadata.sha256[:16],
            source_path=metadata.source_path,
            detected_type="text/plain",
            text=text,
            metadata={"encoding": "utf-8"},
            warnings=[],
        )


class MarkdownParser:
    supported_types = ("text/markdown",)

    def parse(self, file_path: Path, metadata: FileMetadata) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8")
        return ParsedDocument(
            document_id=metadata.sha256[:16],
            source_path=metadata.source_path,
            detected_type="text/markdown",
            text=text.replace("\r\n", "\n"),
            metadata={"encoding": "utf-8", "normalized_newlines": True},
            warnings=[],
        )


class ParserRegistry:
    def __init__(self, parsers: list[DocumentParser]) -> None:
        self._parsers = parsers

    def get(self, detected_type: str) -> DocumentParser:
        for parser in self._parsers:
            if detected_type in parser.supported_types:
                return parser
        raise ValueError(f"No parser registered for {detected_type}")


class ValidatorChain:
    def validate(self, doc: ParsedDocument) -> ValidationResult:
        issues: list[ValidationIssue] = []

        if not doc.text.strip():
            issues.append(ValidationIssue(
                code="EMPTY_CONTENT",
                message="Extracted content is empty",
                severity="error",
            ))

        if len(doc.text.strip()) < 20:
            issues.append(ValidationIssue(
                code="CONTENT_TOO_SHORT",
                message="Extracted content is below the minimum threshold",
                severity="warning",
            ))

        ok = not any(i.severity == "error" for i in issues)
        return ValidationResult(ok=ok, issues=issues)


class IngestionService:
    def __init__(
        self,
        inspector: FileInspector,
        detector: TypeDetector,
        parsers: ParserRegistry,
        validator: ValidatorChain,
        logger: Logger,
    ) -> None:
        self.inspector = inspector
        self.detector = detector
        self.parsers = parsers
        self.validator = validator
        self.logger = logger

    def ingest(self, command: IngestionCommand) -> IngestionResult:
        ingestion_id = f"ing-{int(command.received_at.timestamp())}"

        self.logger.info(
            "ingestion.started",
            correlation_id=command.correlation_id,
            ingestion_id=ingestion_id,
            source_path=command.source_path,
            stage="start",
            status="running",
        )

        try:
            metadata = self.inspector.inspect(command.source_path)
            first_bytes = Path(command.source_path).read_bytes()[:8]
            detected_type = self.detector.detect(metadata, first_bytes)
            parser = self.parsers.get(detected_type)
            parsed = parser.parse(Path(command.source_path), metadata)
            validation = self.validator.validate(parsed)

            warnings = [i.message for i in validation.issues if i.severity == "warning"]
            if not validation.ok:
                self.logger.error(
                    "ingestion.validation.failed",
                    correlation_id=command.correlation_id,
                    ingestion_id=ingestion_id,
                    document_id=parsed.document_id,
                    source_path=command.source_path,
                    stage="content_validation",
                    status="failed",
                    error_code="VALIDATION_ERROR",
                    issues=[i.__dict__ for i in validation.issues],
                )
                return IngestionResult(
                    status="failed",
                    ingestion_id=ingestion_id,
                    document_id=parsed.document_id,
                    source_path=command.source_path,
                    detected_type=detected_type,
                    error_code="VALIDATION_ERROR",
                    message="Document failed validation",
                    warnings=warnings,
                )

            self.logger.info(
                "ingestion.completed",
                correlation_id=command.correlation_id,
                ingestion_id=ingestion_id,
                document_id=parsed.document_id,
                source_path=command.source_path,
                stage="completed",
                status="success",
                detected_type=detected_type,
                warnings=warnings,
            )
            return IngestionResult(
                status="success",
                ingestion_id=ingestion_id,
                document_id=parsed.document_id,
                source_path=command.source_path,
                detected_type=detected_type,
                message="Document ingested successfully",
                warnings=warnings,
            )

        except FileNotFoundError:
            self.logger.error(
                "ingestion.input.failed",
                correlation_id=command.correlation_id,
                ingestion_id=ingestion_id,
                source_path=command.source_path,
                stage="inspect_input",
                status="failed",
                error_code="INPUT_NOT_FOUND",
                message="Source file not found",
            )
            return IngestionResult(
                status="failed",
                ingestion_id=ingestion_id,
                document_id=None,
                source_path=command.source_path,
                detected_type=None,
                error_code="INPUT_NOT_FOUND",
                message="Source file not found",
            )
        except Exception as exc:
            self.logger.error(
                "ingestion.internal.failed",
                correlation_id=command.correlation_id,
                ingestion_id=ingestion_id,
                source_path=command.source_path,
                stage="unknown",
                status="failed",
                error_code="INTERNAL_ERROR",
                message=str(exc),
            )
            return IngestionResult(
                status="failed",
                ingestion_id=ingestion_id,
                document_id=None,
                source_path=command.source_path,
                detected_type=None,
                error_code="INTERNAL_ERROR",
                message="Unexpected internal error",
            )
```

Esse exemplo está deliberadamente desacoplado da UI. Um endpoint HTTP poderia apenas converter JSON de entrada em `IngestionCommand` e chamar `service.ingest(command)`. Um job em fila faria exatamente o mesmo. Essa é a vantagem arquitetural central.

## 13. Exemplo específico para PDF

Para PDF, vale a pena acrescentar validadores e metadados mais ricos. A documentação técnica recente destaca que a extração de PDF é frágil porque o formato armazena apresentação, não estrutura lógica estável, e que PDFs escaneados precisam de OCR antes de seguir para etapas analíticas [3]. Em um pipeline maduro, o parser de PDF deve registrar quantidade de páginas, páginas com texto, possíveis erros por página e indicador de necessidade de OCR.

```python
import fitz  # PyMuPDF
from pathlib import Path


class PdfParser:
    supported_types = ("application/pdf",)

    def parse(self, file_path: Path, metadata: FileMetadata) -> ParsedDocument:
        warnings: list[str] = []
        page_texts: list[str] = []
        pages_with_text = 0

        try:
            with fitz.open(file_path) as pdf:
                if pdf.needs_pass:
                    raise ValueError("PDF_ENCRYPTED")

                for page_number, page in enumerate(pdf, start=1):
                    try:
                        text = page.get_text("text")
                    except Exception as page_exc:
                        warnings.append(f"Page {page_number} failed: {page_exc}")
                        continue

                    if text and text.strip():
                        pages_with_text += 1
                        page_texts.append(f"--- Page {page_number} ---\n{text.strip()}")

                full_text = "\n\n".join(page_texts)
                if not full_text.strip():
                    raise ValueError("CONTENT_TOO_POOR")

                if pages_with_text < len(pdf):
                    warnings.append("Some pages produced no readable text")

                return ParsedDocument(
                    document_id=metadata.sha256[:16],
                    source_path=metadata.source_path,
                    detected_type="application/pdf",
                    text=full_text,
                    metadata={
                        "pages": len(pdf),
                        "pages_with_text": pages_with_text,
                        "parser": "pymupdf",
                        "ocr_recommended": pages_with_text == 0,
                    },
                    warnings=warnings,
                )
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"PARSE_ERROR: {exc}") from exc
```

Esse parser ilustra uma política profissional: não esconder falhas parciais, registrar advertências por página e classificar PDFs sem texto útil como um caso operacional distinto.

## 14. Persistência de artefatos e auditoria

Um pipeline robusto não deve persistir apenas o “texto final”. O ideal é manter um pequeno conjunto de artefatos auditáveis por ingestão.

| Artefato | Finalidade | Retenção sugerida |
|---|---|---|
| **Arquivo original** | Reprocessamento e evidência | Conforme política do domínio |
| **Manifesto de ingestão** | Rastreabilidade ponta a ponta | Longa duração |
| **Texto extraído** | Consumo downstream | Longa ou média duração |
| **Relatório de validação** | Auditoria de qualidade | Média duração |
| **Log indexado** | Observabilidade operacional | Conforme plataforma |
| **Quarentena de erro** | Diagnóstico e retry | Até resolução |

A retenção exata depende do domínio, mas o princípio geral é simples: apagar cedo demais destrói auditabilidade; guardar tudo sem política destrói governança. O equilíbrio deve ser explícito.

## 15. Estratégia de testes

Sem testes, pipelines documentais tendem a degradar silenciosamente. A recomendação é separar a bateria de testes em níveis.

| Nível | Foco | Exemplo |
|---|---|---|
| **Unitário** | Validador, detector e parser isolados | Detectar `INPUT_NOT_FOUND`, validar texto vazio, conferir tipo real |
| **Contrato** | Interface entre chamadores e `IngestionService` | Garantir formato estável de `IngestionResult` |
| **Integração** | Fluxo com arquivos reais | `.txt`, `.md`, PDF textual e PDF escaneado |
| **Regressão** | Casos problemáticos históricos | PDFs com colunas, acentuação ruim, arquivos vazios |
| **Operacional** | Logs, métricas e retries | Verificar presença de `correlation_id` e `source_path` em todos os eventos |

No contexto acadêmico, esse cuidado é particularmente importante quando o pipeline alimenta etapas posteriores de indexação, mineração de texto ou sistemas de recuperação de informação. Sem validação sistemática, erros de extração podem contaminar experimentos e conclusões.

## 16. Antipadrões a evitar

Há alguns erros recorrentes em implementações menos maduras. O primeiro é acoplar o parsing diretamente ao endpoint da UI, tornando impossível reuso em lote ou assíncrono. O segundo é confiar apenas na extensão do arquivo. O terceiro é registrar logs textuais vagos, sem identificadores de correlação e sem `source_path`. O quarto é lançar exceções genéricas sem taxonomia de erro. O quinto é descartar silenciosamente arquivos problemáticos, o que elimina a possibilidade de auditoria. O sexto é tratar todo PDF como se fosse um texto linear confiável, ignorando a complexidade estrutural do formato [3].

## 17. Recomendação final de implementação

A melhor forma de implementar esse pipeline é tratá-lo como um **serviço de aplicação independente**, com um **contrato de entrada explícito**, uma **cadeia de validação em camadas**, um **registro de parsers por tipo**, um **modelo de erro tipado**, **logs JSON estruturados** e um **manifesto de proveniência por ingestão**. Essa abordagem é tecnicamente sólida, operacionalmente auditável e compatível com cenários profissionais e acadêmicos [1] [2] [3].

Se o contexto exigir evolução futura, esse desenho permite adicionar OCR, novos tipos de documento, filas de processamento, métricas, tracing distribuído e políticas avançadas de compliance sem reescrever a base arquitetural. Em outras palavras, ele começa simples, mas cresce corretamente.

## 18. Referências

[1]: https://dagster.io/learn/data-ingestion "Dagster — Data Ingestion: How It Works, Challenges & Best Practices"
[2]: https://www.w3.org/TR/prov-dm/ "W3C — PROV-DM: The PROV Data Model"
[3]: https://www.nutrient.io/blog/pdf-data-extraction-developer-guide/ "Nutrient — Extracting data from PDFs: A comprehensive guide to techniques and tools"
