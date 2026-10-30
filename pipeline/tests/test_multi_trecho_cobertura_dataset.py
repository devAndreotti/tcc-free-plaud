import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

from escolio.benchmark.datasets import load_benchmark_dataset, load_benchmark_suite
from escolio.benchmark.runners import _is_relevant
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document
from escolio.retrieval.indexer import index_note

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / 'data' / 'datasets' / 'multi_trecho_cobertura'
NOTAS_DIR = REPO_ROOT / 'data' / 'datasets' / 'multi_trecho' / 'notas'
PERGUNTAS_PATH = DATASET_DIR / 'perguntas.json'
SUITE_PATH = DATASET_DIR / 'suite.json'


def _load_script(name: str, arquivo: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, DATASET_DIR / arquivo)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registrar antes de executar: o @dataclass do checador consulta sys.modules[__module__].
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _nota_texto(note_id: str) -> str:
    return structure_document(load_document(NOTAS_DIR / f'{note_id}.md')).normalized_text


def test_schema_ids_unicos_e_contagem_por_grupo() -> None:
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    assert len(dataset.samples) == 40
    ids = [sample.sample_id for sample in dataset.samples]
    assert len(ids) == len(set(ids))

    notas = {path.stem for path in NOTAS_DIR.glob('*.md')}
    assert len(notas) == 7
    for sample in dataset.samples:
        assert sample.question.strip().endswith('?'), sample.sample_id
        assert sample.category == 'inferida', sample.sample_id
        assert sample.expected_note_id in notas, sample.sample_id
        assert sample.expected_terms, sample.sample_id
        assert sample.expected_ref, sample.sample_id

    por_tipo = Counter(sample.sample_id.rsplit('-', 1)[0] for sample in dataset.samples)
    assert por_tipo == {'mt-nota': 20, 'mt-notas': 20}


def test_termos_por_nota_sao_a_uniao_e_estao_na_nota_indicada() -> None:
    payload = json.loads(PERGUNTAS_PATH.read_text(encoding='utf-8'))
    notas = {path.stem for path in NOTAS_DIR.glob('*.md')}
    for raw in payload['samples']:
        sid = raw['sample_id']
        por_nota: dict[str, list[str]] = raw['expected_terms_por_nota']
        uniao = [termo for termos in por_nota.values() for termo in termos]
        assert sorted(uniao) == sorted(raw['expected_terms']), sid
        assert raw['expected_note_id'] in por_nota, sid
        for note_id, termos in por_nota.items():
            assert note_id in notas, sid
            texto = _nota_texto(note_id).lower()
            for termo in termos:
                assert termo.lower() in texto, (sid, note_id, termo)
        ref = raw['expected_ref']
        assert ref.lower() in _nota_texto(raw['expected_note_id']).lower(), (sid, ref)


def test_mt_nota_usa_uma_nota_e_nao_cabe_num_chunk() -> None:
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    joins = [s for s in dataset.samples if s.sample_id.startswith('mt-nota-')]
    assert len(joins) == 20
    for sample in joins:
        note = structure_document(load_document(NOTAS_DIR / f'{sample.expected_note_id}.md'))
        chunks = index_note(note, chunk_size=800, overlap=120)
        # Se algum chunk tivesse os dois termos, o scorer atual acertaria e o lote não mediria junção.
        assert not any(_is_relevant(sample, chunk) for chunk in chunks), sample.sample_id


def test_mt_notas_junta_termos_de_pelo_menos_duas_notas() -> None:
    payload = json.loads(PERGUNTAS_PATH.read_text(encoding='utf-8'))
    for raw in payload['samples']:
        if not raw['sample_id'].startswith('mt-notas-'):
            continue
        notas_com_termos = set(raw['expected_terms_por_nota'])
        assert len(notas_com_termos) >= 2, raw['sample_id']
        assert raw['expected_note_id'] in notas_com_termos, raw['sample_id']


def test_splits_por_nota_estao_em_sincronia(tmp_path: Path) -> None:
    gerador = _load_script('gerar_splits_cobertura', 'gerar_splits.py')
    gerados = gerador.gerar(PERGUNTAS_PATH, destino=tmp_path)
    for caminho, amostras in gerados.items():
        versionado = json.loads((DATASET_DIR / caminho).read_text(encoding='utf-8'))
        assert versionado == json.loads((tmp_path / caminho).read_text(encoding='utf-8')), caminho
        assert len(versionado['samples']) == len(amostras)
    total = sum(len(amostras) for amostras in gerados.values())
    assert total == 40


def test_checador_de_termos_passa_no_lote() -> None:
    checker = _load_script('checar_termos_cobertura', 'checar_termos.py')
    resultados = checker.verificar(PERGUNTAS_PATH)
    assert len(resultados) == 40
    falhas = [(r.sample_id, r.erros) for r in resultados if not r.ok]
    assert not falhas


def test_suite_aponta_para_notas_e_datasets_existentes() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    assert suite.suite_name == 'multi-trecho-cobertura-suite'
    assert suite.negative_dataset_path is None
    assert len(suite.cases) == 7

    ids: list[str] = []
    notas_da_suite: set[str] = set()
    for case in suite.cases:
        assert (REPO_ROOT / case.document_path).is_file(), case.case_id
        note = structure_document(load_document(REPO_ROOT / case.document_path))
        notas_da_suite.add(note.note_id)
        dataset = load_benchmark_dataset(REPO_ROOT / case.dataset_path)
        assert dataset.samples, case.case_id
        for sample in dataset.samples:
            assert sample.expected_note_id == note.note_id, sample.sample_id
            ids.append(sample.sample_id)
    assert len(ids) == len(set(ids)) == 40
    assert len(notas_da_suite) == 7
