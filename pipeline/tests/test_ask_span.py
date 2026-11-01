from pathlib import Path

from test_corpus_ask import (
    FakeEmbedder,
    _build_distributed_corpus,
    _search_hit,
    _settings,
)

from escolio.corpus.ask import answer_corpus_with_citations
from escolio.corpus.ask_span import focus_extractive_answer, verify_answer_span
from escolio.corpus.service import index_corpus_path
from escolio.retrieval.models import SearchHit
from escolio.retrieval.search import normalize_query_terms
from escolio.storage.sqlite import init_sqlite

GIRASSOL = "O projeto Girassol foi iniciado em 2019. O orçamento aprovado para o projeto foi de 350 mil reais."


class SpanProvider:
    """Provider com complete(): devolve um span fixo na checagem e uma resposta fixa no answer()."""

    provider_name = "fake"
    model = "fake-model"

    def __init__(self, span: str, answer: str = "[1]") -> None:
        self.span = span
        self.reply = answer
        self.span_calls = 0

    def complete(
        self, messages: list[dict[str, str]], *, temperature: float | None = None
    ) -> str:
        self.span_calls += 1
        if isinstance(self.span, Exception):
            raise self.span
        return self.span

    def answer(
        self, question: str, contexts: list[str], temperature: float | None = None
    ) -> str:
        return self.reply


def _hit(text: str) -> SearchHit:
    return _search_hit("n1::c1", text)


def test_span_copiado_do_trecho_e_verificado_sem_o_rotulo() -> None:
    status, verified = verify_answer_span(
        SpanProvider('Resposta: "350 mil reais"'),
        "Qual o orçamento do Girassol?",
        [_hit(GIRASSOL)],
    )

    assert status == "verified"
    assert verified is not None
    assert (
        verified.sentence == "O orçamento aprovado para o projeto foi de 350 mil reais."
    )


def test_span_nao_eco_ou_inventado_nao_e_verificado() -> None:
    question = "Qual o orçamento do Girassol?"
    for span in ("NAO", "Não.", "orçamento do Girassol", "400 mil reais"):
        assert verify_answer_span(SpanProvider(span), question, [_hit(GIRASSOL)]) == (
            "not_found",
            None,
        ), span


def test_span_com_frases_fora_de_ordem_e_verificado() -> None:
    texto = "O melhor período para visitar Lisboa é entre abril e junho. O bilhete do tram 28 custa 3 euros."
    span = "O bilhete do tram 28 custa 3 euros.\nO melhor período para visitar Lisboa é entre abril e junho."

    # O "NAO" do fim vale para outro trecho que o modelo recebeu junto.
    status, verified = verify_answer_span(
        SpanProvider(span + "\n\nNAO"),
        "Quanto custa o tram 28 e quando ir a Lisboa?",
        [_hit(texto)],
    )

    assert status == "verified"
    assert (
        verified is not None
        and "abril" in verified.sentence
        and "3 euros" in verified.sentence
    )


def test_span_que_repete_a_instrucao_refaz_a_checagem_um_trecho_por_vez() -> None:
    class EchoThenSpan(SpanProvider):
        def complete(
            self, messages: list[dict[str, str]], *, temperature: float | None = None
        ) -> str:
            self.span_calls += 1
            if self.span_calls == 1:
                return "Responda copiando o trecho exato do TEXTO que contem a informacao pedida."
            return "NAO" if "Lisboa" in messages[-1]["content"] else "220 graus"

    provider = EchoThenSpan("")
    hits = [
        _search_hit("n2::c1", "O melhor período para visitar Lisboa é em abril."),
        _hit("Deixe a massa descansar antes de assar a 220 graus."),
    ]
    status, verified = verify_answer_span(
        provider, "Qual a temperatura de assamento do pão?", hits
    )

    assert status == "verified"
    assert verified is not None and verified.hit.chunk.chunk_id == "n1::c1"
    assert provider.span_calls == 3


def test_span_com_ia_fora_do_ar_fica_indisponivel() -> None:
    assert verify_answer_span(
        SpanProvider(TimeoutError("sem rede")), "Qual o orçamento?", [_hit(GIRASSOL)]
    ) == ("unavailable", None)


def _corpus(tmp_path: Path):
    settings = _settings(tmp_path)
    root = tmp_path / "corpus"
    _build_distributed_corpus(root)
    connection = init_sqlite(settings.sqlite_path)
    index_corpus_path(
        root,
        settings=settings,
        connection=connection,
        embedder=FakeEmbedder(),
        recursive=True,
    )
    return connection


def test_parafrase_com_termo_fora_do_corpus_responde_quando_o_span_e_verificado(
    tmp_path: Path,
) -> None:
    connection = _corpus(tmp_path)
    # "cuida" não existe no corpus; a regra de vocabulário recusaria sem IA.
    question = "Quem cuida do runbook do broker?"
    without_ai = answer_corpus_with_citations(
        question, connection=connection, strategy="lexical", top_k=4
    )
    provider = SpanProvider("equipe de Plataforma")
    with_ai = answer_corpus_with_citations(
        question,
        connection=connection,
        strategy="lexical",
        top_k=4,
        answer_provider=provider,
    )

    assert without_ai.reason_for_no_answer == "query_term_not_in_corpus"
    assert with_ai.status == "answer"
    # A IA devolveu só "[1]" na geração: a resposta é a frase do span, não o trecho inteiro.
    assert (
        with_ai.answer
        == "O runbook de operacao do broker ficou sob responsabilidade da equipe de Plataforma."
    )
    assert with_ai.citations[0].note_id.startswith("02")


def test_termo_fora_do_corpus_continua_recusado_quando_a_ia_nao_acha_span(
    tmp_path: Path,
) -> None:
    connection = _corpus(tmp_path)
    response = answer_corpus_with_citations(
        "Qual a senha do broker do pipeline?",
        connection=connection,
        strategy="lexical",
        top_k=4,
        answer_provider=SpanProvider("NAO"),
    )

    assert response.reason_for_no_answer == "query_term_not_in_corpus"


def test_pergunta_com_vocabulario_do_corpus_e_recusada_sem_span(tmp_path: Path) -> None:
    connection = _corpus(tmp_path)
    provider = SpanProvider("NAO", answer="O prazo é de 15 dias corridos [1].")
    response = answer_corpus_with_citations(
        "Qual o prazo do runbook do broker?",
        connection=connection,
        strategy="lexical",
        top_k=4,
        answer_provider=provider,
    )

    assert response.reason_for_no_answer == "no_supported_span"
    assert provider.span_calls == 1


def test_recorte_fica_com_a_frase_que_traz_a_informacao() -> None:
    vendas = (
        "Relatório de vendas do segundo trimestre. A região Nordeste liderou as vendas com 42 por cento do total. "
        "O produto mais vendido foi o modelo Vega, com 1.830 unidades."
    )
    anesia = (
        "O Anesia calcula a dose de sedativo com base no peso do paciente em quilos. "
        "O limite máximo configurado pelo fabricante é de 180 miligramas por sessão."
    )
    q_vendas = "Qual região vendeu mais no trimestre?"
    q_anesia = "Qual a dose máxima de sedativo por sessão no Anesia?"

    assert focus_extractive_answer(
        q_vendas, normalize_query_terms(q_vendas), vendas
    ) == ("A região Nordeste liderou as vendas com 42 por cento do total.")
    assert focus_extractive_answer(
        q_anesia, normalize_query_terms(q_anesia), anesia
    ) == ("O limite máximo configurado pelo fabricante é de 180 miligramas por sessão.")


def test_recorte_nao_mexe_em_pergunta_dupla_nem_sem_informacao_nova() -> None:
    texto = (
        "O bilhete do tram 28 custa 3 euros. O melhor período é entre abril e junho."
    )
    dupla = "Quanto custa o tram 28 e qual o melhor período?"
    sem_info = "A equipe revisou o runbook. O runbook cobre filas."

    assert focus_extractive_answer(dupla, normalize_query_terms(dupla), texto) == texto
    assert (
        focus_extractive_answer(
            "O que o runbook cobre?", ["runbook", "cobre"], sem_info
        )
        == sem_info
    )
