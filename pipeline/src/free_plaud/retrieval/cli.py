import json

import typer
from rich.console import Console

from free_plaud.app.cli_paths import compose_path
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.rag import answer_with_citations

app = typer.Typer(help="Comandos de chunking, indexação e recuperação.", no_args_is_help=True)
console = Console()


def _safe_console_text(text: str) -> str:
    encoding = getattr(console.file, 'encoding', None) or 'utf-8'
    return text.encode(encoding, errors='replace').decode(encoding)


@app.command("chunks")
def chunks(
    path_parts: list[str] = typer.Argument(..., metavar="PATH"),
    chunk_size: int = 800,
    overlap: int = 120,
) -> None:
    """Gera chunks a partir de um documento local."""
    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    generated = index_note(note, chunk_size=chunk_size, overlap=overlap)
    for chunk in generated:
        preview = _safe_console_text(chunk.chunk_text[:120])
        console.print(
            f"[bold]{chunk.chunk_id}[/bold] "
            f"(v{chunk.note_version}, ofs={chunk.char_start}:{chunk.char_end}, {chunk.token_count} tokens) "
            f"-> {preview}"
        )


@app.command("ask")
def ask(
    path_parts: list[str] = typer.Argument(..., metavar="PATH"),
    question: str = typer.Option(..., "--question", "-q", help="Pergunta em linguagem natural."),
    top_k: int = 3,
) -> None:
    """Executa uma pergunta mínima com resposta estruturada e citação obrigatória."""
    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    response = answer_with_citations(note, question, top_k=top_k)
    typer.echo(json.dumps(response.model_dump(mode='json'), ensure_ascii=True, indent=2))
