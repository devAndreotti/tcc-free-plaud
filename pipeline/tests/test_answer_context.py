from escolio.corpus.answer_context import normalize_answer_markers


def test_normalize_answer_markers_troca_lista_de_fontes_por_marcadores_separados() -> None:
    assert normalize_answer_markers('Voce estudou Azure [1, 2].') == 'Voce estudou Azure [1] [2].'
    assert normalize_answer_markers('Dois [3,4,5] e um [1].') == 'Dois [3] [4] [5] e um [1].'


def test_normalize_answer_markers_nao_mexe_em_marcador_simples_nem_em_texto_sem_fonte() -> None:
    assert normalize_answer_markers('Resposta [1]. Outra [2].') == 'Resposta [1]. Outra [2].'
    assert normalize_answer_markers('Dados [2026, 10] sem fonte.') == 'Dados [2026, 10] sem fonte.'
