from pathlib import Path

import pytest


@pytest.fixture()
def sample_text_file(tmp_path: Path) -> Path:
    file_path = tmp_path / 'sample.txt'
    file_path.write_text(
        'Arquitetura de benchmark local-first\n'
        'O projeto valida ingestão, notas e recuperação com citação.\n'
        'O benchmark mede recall e latência.\n',
        encoding='utf-8',
    )
    return file_path
