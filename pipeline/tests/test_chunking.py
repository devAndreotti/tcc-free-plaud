from free_plaud.retrieval.chunking import chunk_text


def test_chunk_text_generates_more_than_one_chunk() -> None:
    text = ' '.join(['benchmark'] * 600)
    chunks = chunk_text('note-1', text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    assert chunks[0].note_id == 'note-1'
    assert chunks[0].chunk_id == 'note-1-0'
