"""Acrescenta chaves de topo a um JSON já gravado, sem perder o resto e sem deixar arquivo pela metade."""

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _ler_objeto(caminho: Path) -> dict[str, Any]:
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'não consegui ler o JSON do compare em {caminho}: {exc}') from None
    if not isinstance(dados, dict):
        raise ValueError(f'{caminho} não é um objeto JSON de compare.')
    return dados


def verificar_comparacao(caminho: Path, comparison_id: str) -> None:
    """Recusa um JSON que não seja da comparação `comparison_id` (ou que não seja um objeto JSON)."""
    dados = _ler_objeto(caminho)
    if dados.get('comparison_id') != comparison_id:
        raise ValueError(
            f'{caminho} é da comparação {dados.get("comparison_id")!r}, não de {comparison_id!r}; '
            'não vou gravar a faithfulness nele.'
        )


def mesclar_chaves_json(caminho: Path, chaves: Mapping[str, Any], *, comparison_id: str | None = None) -> None:
    """Troca ou acrescenta as chaves de topo de `caminho`.

    Escreve num arquivo temporário da mesma pasta e troca pelo original com `os.replace`, então uma
    falha no meio não deixa o JSON truncado. Com `comparison_id`, recusa o arquivo se ele for de outra
    comparação. Qualquer problema de leitura ou de formato vira ValueError.
    """
    dados = _ler_objeto(caminho)
    if comparison_id is not None:
        verificar_comparacao(caminho, comparison_id)
    dados.update(chaves)
    descritor, temporario = tempfile.mkstemp(dir=caminho.parent, prefix=f'.{caminho.name}.', suffix='.tmp')
    try:
        with os.fdopen(descritor, 'w', encoding='utf-8', newline='\n') as arquivo:
            arquivo.write(json.dumps(dados, ensure_ascii=False, indent=2) + '\n')
        os.replace(temporario, caminho)
    except BaseException:
        Path(temporario).unlink(missing_ok=True)
        raise
