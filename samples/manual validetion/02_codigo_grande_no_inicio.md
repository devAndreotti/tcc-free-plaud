# Implementação de Pipeline de Ingestão com Extração de Metadados

Abaixo está a implementação inicial do módulo de ingestão. O código foi escrito durante a fase de prototipagem e ainda não está coberto por testes unitários completos.

```python
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import chardet


@dataclass
class NoteMetadata:
    note_id: str
    title: str
    slug: str
    summary: str
    body: str
    format: str
    file_name: str
    file_hash: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    chunk_ready: bool = False


def compute_file_hash(path: Path) -> str:
    """Calcula SHA-256 dos primeiros 1024 bytes do arquivo."""
    with open(path, "rb") as f:
        seed = f.read(1024)
    return hashlib.sha256(seed).hexdigest()


def detect_encoding(path: Path) -> str:
    """Detecta encoding com fallback para utf-8."""
    with open(path, "rb") as f:
        raw = f.read(4096)
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def normalize_text(text: str) -> str:
    """Normaliza o texto: NFC, espaços duplos, quebras excessivas."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def slugify(title: str) -> str:
    """Gera slug URL-friendly a partir do título."""
    text = unicodedata.normalize("NFD", title)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def extract_title_from_markdown(text: str) -> Optional[str]:
    """Extrai o primeiro H1 do Markdown, ignorando frontmatter."""
    # Remove frontmatter YAML
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def ingest_file(path: Path) -> NoteMetadata:
    fmt = path.suffix.lstrip(".")
    encoding = detect_encoding(path)
    raw_text = path.read_text(encoding=encoding, errors="replace")
    body = normalize_text(raw_text)
    file_hash = compute_file_hash(path)
    note_id = hashlib.sha256(file_hash.encode()).hexdigest()[:16]
    title = extract_title_from_markdown(body) or path.stem
    slug = slugify(title)
    summary = ""  # geração de resumo ainda não implementada
    return NoteMetadata(
        note_id=note_id,
        title=title,
        slug=slug,
        summary=summary,
        body=body,
        format=fmt,
        file_name=path.name,
        file_hash=file_hash,
    )
```

O módulo acima implementa as etapas fundamentais do pipeline: leitura do arquivo com detecção de encoding, normalização de texto, extração de título e geração do `note_id` como hash estável baseado no conteúdo original.

A decisão de usar apenas os primeiros 1.024 bytes para calcular o `file_hash` foi deliberada: em arquivos grandes, isso mantém a operação rápida e, para a grande maioria dos documentos de notas, o início do arquivo é suficientemente único para evitar colisões acidentais. Colisões intencionais (adversariais) não são uma preocupação neste contexto.

---

## Por que o note_id não usa o nome do arquivo

Uma decisão de design importante é que o `note_id` deriva do conteúdo, não do nome do arquivo. Isso garante que renomear um arquivo não invalida referências externas — links entre notas, marcadores, relações em grafos de conhecimento — que apontem para aquele `note_id`.

O custo dessa escolha é que dois arquivos com conteúdo idêntico gerarão o mesmo `note_id`. No contexto de um sistema de notas pessoal, isso é aceitável e até desejável (deduplicação automática). Para sistemas colaborativos com múltiplos usuários, seria necessário incluir um namespace por usuário no cálculo do hash.

---

## Próximas Etapas

1. Implementar a geração de resumo (linha marcada como pendente).
2. Adicionar suporte a extração de frontmatter YAML via `python-frontmatter`.
3. Criar testes unitários para os casos extremos: arquivo vazio, arquivo só com frontmatter, arquivo com encoding Windows-1252.
4. Avaliar se a função `normalize_text` deve preservar quebras de linha intencionais em blocos de código.
