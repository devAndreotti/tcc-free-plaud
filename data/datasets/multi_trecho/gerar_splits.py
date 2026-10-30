"""Gera os arquivos derivados de perguntas.json.

- por_nota/<note_id>.json: perguntas positivas de cada nota (o runner mede cada dataset contra a
  nota do caso, então um arquivo com perguntas de várias notas contaminaria o resultado);
- negativas.json: as 30 perguntas category 'negativa' (usado por negative_dataset_path do suite).

Uso: python data/datasets/multi_trecho/gerar_splits.py (não precisa do pacote escolio).
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
    saidas: dict[str, list[dict]] = {}

    negativas = [s for s in payload['samples'] if s.get('category') == 'negativa']
    saidas['negativas.json'] = negativas

    por_nota: dict[str, list[dict]] = {}
    for sample in payload['samples']:
        if sample.get('category') == 'negativa':
            continue
        por_nota.setdefault(sample['expected_note_id'], []).append(sample)
    for note_id, amostras in sorted(por_nota.items()):
        saidas[f'por_nota/{note_id}.json'] = amostras

    for caminho, amostras in saidas.items():
        nome = Path(caminho).stem
        alvo = destino / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        dataset = {'dataset_name': f'multi-trecho-{nome}', 'samples': amostras}
        alvo.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return saidas


if __name__ == '__main__':
    for caminho, amostras in gerar().items():
        print(f'{caminho}: {len(amostras)} amostras')
