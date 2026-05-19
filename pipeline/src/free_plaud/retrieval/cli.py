import json

import typer
from rich.console import Console

from free_plaud.app.cli_paths import compose_path
from free_plaud.app.config import get_settings
from free_plaud.app.paths import ensure_runtime_dirs
from free_plaud.ingest.loaders import load_document
from free_plaud.notes.structurer import structure_document
from free_plaud.providers.embed import get_embedder
from free_plaud.retrieval.indexer import index_note
from free_plaud.retrieval.rag import answer_with_citations
from free_plaud.retrieval.search import open_semantic_search, semantic_search
from free_plaud.storage.vector import LocalVectorStore

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
    strategy: str = typer.Option('lexical', '--strategy', '-s', help="Estrategia de retrieval: lexical, vector ou hybrid."),
) -> None:
    """Executa uma pergunta mínima com resposta estruturada e citação obrigatória."""
    if strategy not in {'lexical', 'vector', 'hybrid'}:
        raise typer.BadParameter("strategy deve ser 'lexical', 'vector' ou 'hybrid'.")

    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    vector_store = None
    embedder = None
    if strategy in {'vector', 'hybrid'}:
        settings = get_settings()
        ensure_runtime_dirs(settings)
        vector_store = LocalVectorStore(
            settings.vector_store_dir,
            collection_name=settings.vector_collection_name,
        )
        embedder = get_embedder(settings.embedding_model)
    response = answer_with_citations(
        note,
        question,
        top_k=top_k,
        strategy=strategy,
        vector_store=vector_store,
        embedder=embedder,
    )
    typer.echo(json.dumps(response.model_dump(mode='json'), ensure_ascii=True, indent=2))


@app.command("index")
def index(
    path_parts: list[str] = typer.Argument(..., metavar="PATH"),
    chunk_size: int = 800,
    overlap: int = 120,
) -> None:
    """Indexa um documento no vector store local."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    vector_store = LocalVectorStore(
        settings.vector_store_dir,
        collection_name=settings.vector_collection_name,
    )
    embedder = get_embedder(settings.embedding_model)
    path = compose_path(path_parts)
    document = load_document(path)
    note = structure_document(document)
    chunks = index_note(note, chunk_size=chunk_size, overlap=overlap)
    embeddings = embedder.embed([chunk.chunk_text for chunk in chunks])
    vector_store.upsert_chunks(chunks, embeddings, embedding_model=embedder.model_name)
    typer.echo(
        json.dumps(
            {
                'note_id': note.note_id,
                'chunks_indexed': len(chunks),
                'embedding_model': embedder.model_name,
                'vector_collection_name': settings.vector_collection_name,
                'vector_entries_count': vector_store.count(),
            },
            ensure_ascii=True,
            indent=2,
        )
    )


@app.command("semantic-search")
def semantic_search_command(
    query: str = typer.Option(..., "--query", "-q", help="Consulta em linguagem natural."),
    top_k: int = 5,
    note_id: str | None = typer.Option(None, "--note-id", help="Filtra a busca por uma nota especifica."),
) -> None:
    """Executa busca semântica no vector store local já persistido."""
    settings = get_settings()
    ensure_runtime_dirs(settings)
    vector_store = LocalVectorStore(
        settings.vector_store_dir,
        collection_name=settings.vector_collection_name,
    )
    embedder = get_embedder(settings.embedding_model)
    hits = (
        semantic_search(query, vector_store, embedder, top_k=top_k, note_id=note_id)
        if note_id
        else open_semantic_search(query, vector_store, embedder, top_k=top_k)
    )
    typer.echo(
        json.dumps(
            [
                {
                    'chunk_id': hit.chunk.chunk_id,
                    'note_id': hit.chunk.note_id,
                    'note_version': hit.chunk.note_version,
                    'score': hit.score,
                    'distance': hit.distance,
                    'matched_terms': hit.matched_terms,
                    'term_coverage': hit.term_coverage,
                    'strategy': hit.strategy,
                    'char_start': hit.chunk.char_start,
                    'char_end': hit.chunk.char_end,
                    'snippet': hit.chunk.chunk_text[:180],
                }
                for hit in hits
            ],
            ensure_ascii=True,
            indent=2,
        )
    )
