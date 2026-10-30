"""Faithfulness semântica: quebra em afirmações, parser do veredito e score com juiz falso (sem rede).

O relatório, o cliente HTTP do juiz e o CLI ficam em test_faithfulness_relatorio.py.
"""

import json
from pathlib import Path

from escolio.benchmark.datasets import load_benchmark_suite
from escolio.benchmark.faithfulness import (
    build_judge_prompt,
    faithfulness_score,
    judge_claim,
    parse_verdict,
    split_claims,
    verify_claims,
)
from escolio.benchmark.runners import BenchmarkComparisonResult, compare_benchmark_suite
from escolio.storage.sqlite import init_sqlite
from escolio.storage.vector import LocalVectorStore


class FakeEmbedder:
    model_name = 'fake-hash'

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for token in text.lower().split():
                vector[sum(ord(char) for char in token) % len(vector)] += 1.0
            embeddings.append(vector)
        return embeddings


class JuizFalso:
    """Juiz determinístico: SUPORTADO quando a afirmação contém uma das palavras-chave."""

    def __init__(self, palavras: tuple[str, ...] = (), resposta_fixa: str | None = None) -> None:
        self.palavras = palavras
        self.resposta_fixa = resposta_fixa
        self.chamadas: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.chamadas.append(prompt)
        if self.resposta_fixa is not None:
            return self.resposta_fixa
        afirmacao = prompt.split('AFIRMACAO:\n', 1)[1].split('\n\nVeredito', 1)[0].lower()
        return 'SUPORTADO' if any(palavra in afirmacao for palavra in self.palavras) else 'NAO_SUPORTADO'


def _suite_com_corpus(tmp_path: Path) -> Path:
    documentos = {
        'kafka': '# Kafka\n\nO Apache Kafka foi adotado como broker padrao da plataforma de eventos.\n',
        'redis': '# Redis\n\nO timeout do Redis em staging esta configurado para trinta segundos.\n',
    }
    casos = []
    for nome, texto in documentos.items():
        (tmp_path / f'{nome}.md').write_text(texto, encoding='utf-8')
        (tmp_path / f'{nome}.json').write_text(
            json.dumps(
                {
                    'dataset_name': nome,
                    'samples': [
                        {
                            'sample_id': f'{nome}-1',
                            'question': f'Qual a configuracao do {nome}?',
                            'expected_note_id': nome,
                            'expected_terms': [nome.capitalize()],
                        }
                    ],
                }
            ),
            encoding='utf-8',
        )
        casos.append({'case_id': nome, 'document_path': f'{nome}.md', 'dataset_path': f'{nome}.json'})
    (tmp_path / 'negativas.json').write_text(
        json.dumps({'dataset_name': 'negativas', 'samples': [{'sample_id': 'neg-1', 'question': 'Qual a receita anual do refeitorio?', 'category': 'negativa'}]}),
        encoding='utf-8',
    )
    suite_path = tmp_path / 'suite.json'
    suite_path.write_text(
        json.dumps({'suite_name': 'faith-suite', 'cases': casos, 'negative_dataset_path': 'negativas.json'}),
        encoding='utf-8',
    )
    return suite_path


def _comparar(tmp_path: Path, nome: str, *, keep_answers: bool) -> BenchmarkComparisonResult:
    pasta = tmp_path / nome
    return compare_benchmark_suite(
        load_benchmark_suite(_suite_com_corpus(tmp_path)),
        workspace_dir=tmp_path,
        connection=init_sqlite(pasta / 'benchmark.sqlite3'),
        top_k=3,
        chunk_size=200,
        overlap=20,
        vector_store=LocalVectorStore(pasta / 'vector_store', collection_name=f'{nome}_compare'),
        embedder=FakeEmbedder(),
        keep_answers=keep_answers,
    )


def test_compare_sem_flag_nao_grava_resposta_nem_contextos(tmp_path: Path) -> None:
    resultado = _comparar(tmp_path, 'sem', keep_answers=False)
    linhas = resultado.corpus.queries['hybrid']
    assert linhas and all(linha.answer is None and linha.contexts is None for linha in linhas)


def test_compare_com_flag_grava_resposta_e_trechos_citados(tmp_path: Path) -> None:
    resultado = _comparar(tmp_path, 'com', keep_answers=True)
    respondidas = [linha for linha in resultado.corpus.queries['hybrid'] if linha.answered]
    assert respondidas, 'a suíte de teste precisa ter perguntas respondidas'
    for linha in respondidas:
        assert linha.answer and linha.answer.strip()
        assert linha.contexts, 'a resposta deve trazer os trechos que ela cita'
        assert all(isinstance(trecho, str) and trecho.strip() for trecho in linha.contexts)
    # Sobrevive ao JSON que o report-ia e o faithfulness leem.
    relido = BenchmarkComparisonResult.model_validate_json(resultado.model_dump_json())
    assert relido.corpus.queries['hybrid'][0].model_dump() == resultado.corpus.queries['hybrid'][0].model_dump()


def test_split_claims_remove_marcadores_e_separa_sentencas() -> None:
    assert split_claims('O Kafka é o broker [1]. O Redis expira em 30 s [2][3].') == [
        'O Kafka é o broker.',
        'O Redis expira em 30 s.',
    ]
    assert split_claims('Primeira linha\nSegunda linha') == ['Primeira linha', 'Segunda linha']
    assert split_claims('[1] [2]\n\n  ') == []
    assert split_claims('') == []


def test_parse_verdict_tolera_caixa_acento_markdown_e_ruido() -> None:
    assert parse_verdict('SUPORTADO') == 'suportado'
    assert parse_verdict('suportado.') == 'suportado'
    assert parse_verdict('NAO_SUPORTADO') == 'nao_suportado'
    assert parse_verdict('NÃO SUPORTADO') == 'nao_suportado'
    assert parse_verdict('**Veredito: nao_suportado.**') == 'nao_suportado'
    assert parse_verdict('Não é suportado pelos trechos.') == 'nao_suportado'
    assert parse_verdict('A afirmação não foi suportada.') == 'nao_suportado'
    assert parse_verdict('Suportada.') == 'suportado'
    # Juiz que ecoa as opções: vale a última escolha.
    assert parse_verdict('SUPORTADO ou NAO_SUPORTADO. Resposta: NAO_SUPORTADO') == 'nao_suportado'
    assert parse_verdict('Não sei dizer.') is None
    assert parse_verdict('') is None


def test_judge_claim_usa_o_veredito_e_nao_chama_o_juiz_sem_contexto() -> None:
    juiz = JuizFalso(palavras=('kafka',))
    assert judge_claim('O Kafka é o broker.', ['Apache Kafka é o broker padrão.'], juiz) is True
    assert judge_claim('O Redis expira.', ['Apache Kafka é o broker padrão.'], juiz) is False
    assert '[1] Apache Kafka' in juiz.chamadas[0]

    juiz_vazio = JuizFalso(resposta_fixa='SUPORTADO')
    assert judge_claim('Qualquer coisa.', [], juiz_vazio) is False
    assert judge_claim('Qualquer coisa.', ['   '], juiz_vazio) is False
    assert juiz_vazio.chamadas == []


def test_faithfulness_score_fracao_de_afirmacoes_suportadas() -> None:
    juiz = JuizFalso(palavras=('kafka',))
    score = faithfulness_score('O Kafka é o broker [1]. O Redis expira em 30 s [2].', ['Kafka broker.', 'Redis timeout.'], juiz)
    assert score == 0.5
    assert len(juiz.chamadas) == 2  # uma chamada por afirmação


def test_faithfulness_score_bordas_como_lexical_groundedness() -> None:
    juiz = JuizFalso(palavras=('x',))
    assert faithfulness_score('', ['trecho'], juiz) == 1.0
    assert faithfulness_score('[1]', ['trecho'], juiz) == 1.0  # só marcador não é afirmação
    assert faithfulness_score('Afirmação qualquer aqui.', [], juiz) == 0.0
    assert juiz.chamadas == []


def test_veredito_ilegivel_conta_como_nao_suportado_e_fica_marcado() -> None:
    juiz = JuizFalso(resposta_fixa='talvez, não tenho certeza')
    verificacoes = verify_claims('O Kafka é o broker.', ['Kafka broker.'], juiz)
    assert [item.verdict for item in verificacoes] == ['indeterminado']
    assert faithfulness_score('O Kafka é o broker.', ['Kafka broker.'], juiz) == 0.0


def test_judge_prompt_e_pedido_com_veredito_estrito_em_pt() -> None:
    prompt = build_judge_prompt('O Kafka é o broker.', ['Kafka broker.', '  '])
    assert 'SUPORTADO ou NAO_SUPORTADO' in prompt
    assert prompt.endswith('Veredito:')
    assert '[1] Kafka broker.' in prompt
