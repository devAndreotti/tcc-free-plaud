"""Gera por_nota/<note_id>.json a partir de perguntas.json.

O runner mede cada caso da suite contra a nota do caso, então cada pergunta vai só para o arquivo da
nota primária (expected_note_id). Não há negativas neste lote.

Uso: python data/datasets/multi_trecho_cobertura/gerar_splits.py (não precisa do pacote escolio).
Os arquivos gerados são versionados; rode de novo sempre que perguntas.json mudar.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERGUNTAS = HERE / 'perguntas.json'


def gerar(perguntas_path: Path = PERGUNTAS, destino: Path = HERE) -> dict[str, list[dict]]:
    """Escreve os splits e devolve {caminho_relativo: amostras} para teste de sincronia."""
    payload = json.loads(perguntas_path.read_text(encoding='utf-8'))
    por_nota: dict[str, list[dict]] = {}
    for sample in payload['samples']:
        por_nota.setdefault(sample['expected_note_id'], []).append(sample)

    saidas: dict[str, list[dict]] = {}
    for note_id, amostras in sorted(por_nota.items()):
        caminho = f'por_nota/{note_id}.json'
        saidas[caminho] = amostras
        alvo = destino / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        dataset = {'dataset_name': f'multi-trecho-cobertura-{note_id}', 'samples': amostras}
        alvo.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return saidas


if __name__ == '__main__':
    for caminho, amostras in gerar().items():
        print(f'{caminho}: {len(amostras)} amostras')
