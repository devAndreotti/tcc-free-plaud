from free_plaud.notes.schemas import Note
        from free_plaud.retrieval.indexer import index_note
        from free_plaud.retrieval.search import lexical_search


        def answer_with_citations(note: Note, question: str, top_k: int = 3) -> str:
            """Monta uma resposta mínima com citações baseadas em chunks recuperados."""
            chunks = index_note(note)
            hits = lexical_search(question, chunks, top_k=top_k)
            if not hits:
                return 'Não encontrei evidência suficiente na nota para responder com citação.'

            citations = '
'.join(f'- [{chunk.chunk_id}] {chunk.chunk_text[:180]}' for chunk in hits)
            return (
                'Resposta preliminar baseada apenas na nota indexada.

'
                'Trechos citados:
'
                f'{citations}'
            )
