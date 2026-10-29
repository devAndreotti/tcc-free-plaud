from escolio.corpus.answer_context import citation_snippet, normalize_answer_markers


def test_normalize_answer_markers_troca_lista_de_fontes_por_marcadores_separados() -> None:
    assert normalize_answer_markers('Voce estudou Azure [1, 2].') == 'Voce estudou Azure [1] [2].'
    assert normalize_answer_markers('Dois [3,4,5] e um [1].') == 'Dois [3] [4] [5] e um [1].'


def test_normalize_answer_markers_nao_mexe_em_marcador_simples_nem_em_texto_sem_fonte() -> None:
    assert normalize_answer_markers('Resposta [1]. Outra [2].') == 'Resposta [1]. Outra [2].'
    assert normalize_answer_markers('Dados [2026, 10] sem fonte.') == 'Dados [2026, 10] sem fonte.'


def test_citation_snippet_traz_a_passagem_do_claim_e_nao_so_o_comeco_do_chunk() -> None:
    claim = 'A versão 2.1, lançada em março, trouxe o painel novo.'
    chunk = 'Introdução sobre a instalação e a configuração inicial do sistema. ' * 8 + claim

    assert citation_snippet(chunk, claim) == claim
    # Negrito no chunk: o claim não aparece literal, então a janela segue o primeiro termo dele.
    chunk_negrito = 'Texto antigo sem relação com o assunto. ' * 12 + '**Redis** guarda as sessões no cache.'
    snippet = citation_snippet(chunk_negrito, 'Redis guarda as sessões no cache.')
    assert 'Redis' in snippet
    assert len(snippet) <= 400
