import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from escolio.benchmark.datasets import load_benchmark_dataset, load_benchmark_suite
from escolio.benchmark.runners import _is_relevant
from escolio.ingest.loaders import load_document
from escolio.notes.structurer import structure_document
from escolio.retrieval.indexer import index_note

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / 'data' / 'datasets' / 'multi_trecho'
PERGUNTAS_PATH = DATASET_DIR / 'perguntas.json'
SUITE_PATH = DATASET_DIR / 'suite.json'
NEGATIVAS_PATH = DATASET_DIR / 'negativas.json'


def _load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, DATASET_DIR / f'{name}.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registrar antes de executar: o @dataclass do checador consulta sys.modules[__module__].
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _positivas():
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    return [sample for sample in dataset.samples if sample.category != 'negativa']


def test_perguntas_schema_e_ids_unicos() -> None:
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    ids = [sample.sample_id for sample in dataset.samples]
    assert len(ids) == len(set(ids))

    notas = {path.stem for path in (DATASET_DIR / 'notas').glob('*.md')}
    assert len(notas) >= 6
    for sample in dataset.samples:
        assert sample.question.strip().endswith('?'), sample.sample_id
        assert sample.category in {'direta', 'inferida', 'negativa'}, sample.sample_id
        if sample.category == 'negativa':
            assert sample.expected_note_id is None, sample.sample_id
            assert not sample.expected_terms, sample.sample_id
        else:
            assert sample.expected_note_id in notas, sample.sample_id
            assert sample.expected_terms, sample.sample_id
            assert sample.expected_ref, sample.sample_id


def test_proporcao_30_positivas_30_negativas() -> None:
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    assert len(dataset.samples) == 60

    negativas = [s for s in dataset.samples if s.category == 'negativa']
    positivas = [s for s in dataset.samples if s.category != 'negativa']
    assert len(positivas) == 30
    assert len(negativas) == 30

    por_tipo = {'unica': 0, 'mt-nota': 0, 'mt-notas': 0}
    for sample in positivas:
        tipo = sample.sample_id.rsplit('-', 1)[0]
        assert tipo in por_tipo, sample.sample_id
        por_tipo[tipo] += 1
    assert por_tipo == {'unica': 10, 'mt-nota': 10, 'mt-notas': 10}

    # Negativas com entidades reais das notas (perigosas) devem existir.
    nomes_reais = ('Júlia Neves', 'Ana Lima Furtado', 'Larissa Quintela', 'Diego Sampaio', 'Heitor Rocha')
    perigosas = [s for s in negativas if any(nome in s.question for nome in nomes_reais)]
    assert len(perigosas) >= 5


def test_termos_e_referencias_presentes_na_nota_esperada() -> None:
    checker = _load_script('checar_termos')
    resultados = checker.verificar(PERGUNTAS_PATH)
    assert len(resultados) == 30
    falhas = [(r.sample_id, r.missing, r.ref_found) for r in resultados if not r.ok]
    assert not falhas


def test_perguntas_unicas_sao_alcancaveis_por_um_chunk() -> None:
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    for sample in dataset.samples:
        if sample.category != 'direta':
            continue
        note = structure_document(load_document(DATASET_DIR / 'notas' / f'{sample.expected_note_id}.md'))
        chunks = index_note(note, chunk_size=800, overlap=120)
        assert any(_is_relevant(sample, chunk) for chunk in chunks), sample.sample_id


def test_joins_da_mesma_nota_exigem_mais_de_um_chunk() -> None:
    # Propriedade do dataset: os dois trechos não cabem num chunk 800/120, então a pergunta
    # só fica respondível juntando chunks distintos.
    dataset = load_benchmark_dataset(PERGUNTAS_PATH)
    joins = [s for s in dataset.samples if s.sample_id.startswith('mt-nota-')]
    assert len(joins) == 10
    for sample in joins:
        note = structure_document(load_document(DATASET_DIR / 'notas' / f'{sample.expected_note_id}.md'))
        chunks = index_note(note, chunk_size=800, overlap=120)
        assert not any(_is_relevant(sample, chunk) for chunk in chunks), sample.sample_id


def test_notas_sinteticas_tamanho_e_datas() -> None:
    notas = sorted((DATASET_DIR / 'notas').glob('*.md'))
    assert 6 <= len(notas) <= 8
    for path in notas:
        texto = path.read_text(encoding='utf-8')
        assert 1000 <= len(texto) <= 3000, path.name
        # Datas explícitas dd/mm/aaaa no corpo.
        assert any(part[2:3] == '/' and part[5:6] == '/' for part in texto.split()), path.name


def test_splits_derivados_estao_em_sincronia_com_perguntas(tmp_path: Path) -> None:
    gerador = _load_script('gerar_splits')
    gerados = gerador.gerar(PERGUNTAS_PATH, destino=tmp_path)
    for caminho, amostras in gerados.items():
        versionado = json.loads((DATASET_DIR / caminho).read_text(encoding='utf-8'))
        gerado = json.loads((tmp_path / caminho).read_text(encoding='utf-8'))
        assert versionado == gerado, caminho
        assert len(versionado['samples']) == len(amostras)


def test_suite_aponta_para_notas_e_datasets_existentes() -> None:
    suite = load_benchmark_suite(SUITE_PATH)
    assert suite.suite_name == 'multi-trecho-retrieval-suite'
    assert suite.negative_dataset_path is not None

    positivas_ids: set[str] = set()
    for case in suite.cases:
        assert (REPO_ROOT / case.document_path).is_file(), case.case_id
        dataset = load_benchmark_dataset(REPO_ROOT / case.dataset_path)
        note = structure_document(load_document(REPO_ROOT / case.document_path))
        assert len(dataset.samples) >= 3, case.case_id
        for sample in dataset.samples:
            assert sample.expected_note_id == note.note_id, sample.sample_id
            positivas_ids.add(sample.sample_id)
    assert len(positivas_ids) == 30

    negativas = load_benchmark_dataset(REPO_ROOT / suite.negative_dataset_path)
    assert len(negativas.samples) == 30
    assert all(s.category == 'negativa' and s.expected_note_id is None for s in negativas.samples)
    assert (REPO_ROOT / suite.negative_dataset_path) == NEGATIVAS_PATH
