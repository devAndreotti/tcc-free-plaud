from pathlib import Path

from escolio.corpus.discovery import discover_corpus_files


def test_discover_corpus_files_keeps_supported_top_level_files_sorted(tmp_path: Path) -> None:
    root = tmp_path / 'corpus'
    root.mkdir()
    (root / 'b.md').write_text('# B\n', encoding='utf-8')
    (root / 'a.txt').write_text('A\n', encoding='utf-8')
    (root / 'planilha.xlsx').write_text('x\n', encoding='utf-8')
    nested = root / 'nested'
    nested.mkdir()
    (nested / 'c.md').write_text('# C\n', encoding='utf-8')

    result = discover_corpus_files(root, recursive=False)

    assert [path.name for path in result.files] == ['a.txt', 'b.md']
    assert {item.path for item in result.skipped} == {str(nested), str(root / 'planilha.xlsx')}


def test_discover_corpus_files_recurses_and_ignores_runtime_directories(tmp_path: Path) -> None:
    root = tmp_path / 'corpus'
    nested = root / 'nested'
    git_dir = root / '.git'
    node_modules = root / 'node_modules'
    vector_store = root / 'data' / 'results' / 'vector_store'
    for directory in (nested, git_dir, node_modules, vector_store):
        directory.mkdir(parents=True)
    (root / 'a.md').write_text('# A\n', encoding='utf-8')
    (nested / 'b.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
    (git_dir / 'ignored.md').write_text('# Ignored\n', encoding='utf-8')
    (node_modules / 'ignored.txt').write_text('ignored\n', encoding='utf-8')
    (vector_store / 'ignored.md').write_text('# Ignored\n', encoding='utf-8')

    result = discover_corpus_files(root, recursive=True)

    assert [path.name for path in result.files] == ['a.md', 'b.pdf']
    skipped_paths = {item.path for item in result.skipped}
    assert str(git_dir) in skipped_paths
    assert str(node_modules) in skipped_paths
    assert str(vector_store) in skipped_paths
