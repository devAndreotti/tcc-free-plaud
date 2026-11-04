import json
import sqlite3
from pathlib import Path

from escolio.app.config import Settings
from escolio.app.vaults import create_vault
from escolio.app.vaults_overview import vaults_overview
from escolio.benchmark.history import load_benchmark_run, negative_subtypes
from escolio.storage.sqlite import init_sqlite


def _settings(tmp_path: Path) -> Settings:
    return Settings(workspace_dir=tmp_path, data_dir=tmp_path / 'data', results_dir=tmp_path / 'results')


def _grava_notas(banco: Path, notas: list[tuple[str, str]], raiz: str) -> None:
    init_sqlite(banco).close()
    con = sqlite3.connect(banco)
    con.row_factory = None
    colunas = [linha[1] for linha in con.execute('PRAGMA table_info(notes)')]
    obrigatorias = [linha[1] for linha in con.execute('PRAGMA table_info(notes)') if linha[3]]
    for i, (titulo, caminho) in enumerate(notas):
        valores = {c: '' for c in obrigatorias}
        valores.update(note_id=f'n{i}', note_version=1, title=titulo, source_path=caminho)
        chaves = [c for c in colunas if c in valores]
        con.execute(f"INSERT INTO notes ({','.join(chaves)}) VALUES ({','.join('?' * len(chaves))})", [valores[c] for c in chaves])
    con.execute('INSERT OR REPLACE INTO corpus_roots (root) VALUES (?)', (raiz,))
    con.commit()
    con.close()


def test_visao_conta_pastas_e_nao_mexe_na_vault_vazia(tmp_path: Path) -> None:
    base = _settings(tmp_path)
    vault = create_vault('Estudos', 'notes', 'teal', [], base)
    banco = Path(vault.sqlite_path) if vault.sqlite_path else tmp_path / 'data' / 'vaults' / vault.id / 'escolio.sqlite3'
    banco.parent.mkdir(parents=True, exist_ok=True)
    _grava_notas(banco, [
        ('Docker', r'C:\Notas\Área de TI\Docker.md'),
        ('OSPF', 'C:/Notas/Área de TI/Redes/OSPF.md'),
        ('Solta', 'C:/Notas/Solta.md'),
    ], r'C:\Notas')
    create_vault('Vazia', 'notes', 'rose', [], base)

    visao = vaults_overview(base)
    por_nome = {v['name']: v for v in visao['vaults']}

    estudos = por_nome['Estudos']
    assert estudos['note_count'] == 3
    assert estudos['folders'] == [{'name': 'Área de TI', 'count': 2}, {'name': '', 'count': 1}]
    assert {'id': 'n0', 'title': 'Docker', 'folder': 'Área de TI'} in estudos['notes']
    assert por_nome['Vazia']['note_count'] == 0
    assert por_nome['Vazia']['notes'] == []


def _suite(tmp_path: Path, com_tipo: bool = True) -> Path:
    negativas = [{'sample_id': 'x', 'question': 'Q?', 'category': 'negativa', **({'subtipo': 'quase-acerto'} if com_tipo else {})}]
    pasta = tmp_path / 'data' / 'datasets' / 'lote'
    pasta.mkdir(parents=True)
    (pasta / 'neg.json').write_text(json.dumps(negativas), encoding='utf-8')
    suite = pasta / 'suite.json'
    suite.write_text(json.dumps({'suite_name': 'minha', 'cases': [], 'negative_dataset_path': 'data/datasets/lote/neg.json'}), encoding='utf-8')
    return suite


def test_tipos_das_negativas_vem_do_dataset(tmp_path: Path) -> None:
    settings = Settings(workspace_dir=tmp_path, results_dir=tmp_path / 'results', datasets_dir=tmp_path / 'data' / 'datasets')
    suite = _suite(tmp_path)
    assert negative_subtypes(suite, settings=settings) == {'x': 'quase-acerto'}


def test_rodada_antiga_ganha_os_tipos_pelo_nome_da_suite(tmp_path: Path) -> None:
    settings = Settings(workspace_dir=tmp_path, results_dir=tmp_path / 'results', datasets_dir=tmp_path / 'data' / 'datasets')
    _suite(tmp_path)
    settings.results_dir.mkdir()
    (settings.results_dir / 'cmp-aaaaaaaaaaaa.json').write_text(json.dumps({'comparison_id': 'cmp-aaaaaaaaaaaa', 'suite_name': 'minha'}), encoding='utf-8')
    assert load_benchmark_run('cmp-aaaaaaaaaaaa', settings=settings)['negative_subtypes'] == {'x': 'quase-acerto'}


def test_suite_sem_tipos_nao_inventa_nada(tmp_path: Path) -> None:
    settings = Settings(workspace_dir=tmp_path, results_dir=tmp_path / 'results', datasets_dir=tmp_path / 'data' / 'datasets')
    assert negative_subtypes(_suite(tmp_path, com_tipo=False), settings=settings) == {}
