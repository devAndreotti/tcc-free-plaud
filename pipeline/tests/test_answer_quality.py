from escolio.providers.answer_quality import is_echoed_question, is_echoed_title, is_no_answer_sentinel

CISCO_CONTEXT = (
    '[1]\nsource_path: cisco.md\ntitle: Cisco — Trilha de Cursos e Certificações\nnote_id: cisco\nchunk_id: cisco::1\n'
    'claim_extrativo: A trilha reúne cursos de redes.\n'
    'trecho:\n# Cisco — Trilha de Cursos e Certificações\n\nA trilha reúne cursos de redes e certificações oficiais.'
)
PRAZO_CONTEXT = (
    '[1]\nsource_path: prazo.md\ntitle: Prazo de entrega\nnote_id: prazo\nchunk_id: prazo::1\n'
    'claim_extrativo: O prazo de entrega é de 15 dias úteis.\n'
    'trecho:\n# Prazo de entrega\n\nO prazo de entrega é de 15 dias úteis.'
)


def test_sentinela_no_comeco_e_abstencao_mesmo_sem_a_palavra_no_contexto() -> None:
    assert is_no_answer_sentinel('NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.', [PRAZO_CONTEXT])


def test_sentinela_no_meio_e_abstencao_quando_o_contexto_nao_tem_a_palavra() -> None:
    resposta = 'O prazo de entrega e de 15 dias uteis [1]. NAO_ENCONTRADO: os dados recuperados nao sustentam resposta.'

    assert is_no_answer_sentinel(resposta, [PRAZO_CONTEXT])


def test_sentinela_no_meio_nao_e_abstencao_quando_o_contexto_tem_a_palavra() -> None:
    contexto = 'O modo de busca devolve NAO_ENCONTRADO quando nada casa com a pergunta.'

    assert not is_no_answer_sentinel('O modo de busca devolve NAO_ENCONTRADO quando nada casa [1].', [contexto])


def test_sentinela_exige_a_palavra_inteira_e_sem_resposta_nao_dispara() -> None:
    assert not is_no_answer_sentinel('Os arquivos NAO_ENCONTRADOS ficam na lixeira.', [PRAZO_CONTEXT])
    assert not is_no_answer_sentinel('O prazo de entrega e de 15 dias uteis [1].', [PRAZO_CONTEXT])


def test_titulo_copiado_do_cabecalho_e_do_heading_nao_e_resposta() -> None:
    assert is_echoed_title('Cisco — Trilha de Cursos e Certificações', [CISCO_CONTEXT])
    assert is_echoed_title('**Cisco - Trilha de Cursos e Certificacoes**', [CISCO_CONTEXT])


def test_titulo_so_no_cabecalho_title_do_contexto_tambem_conta() -> None:
    contexto = '[1]\nsource_path: cisco.md\ntitle: Cisco Trilha Cursos\nnote_id: cisco\ntrecho:\nTexto sem heading.'

    assert is_echoed_title('Cisco Trilha Cursos', [contexto])
    assert is_echoed_title('Título: Cisco Trilha Cursos', [contexto])


def test_titulo_copiado_com_trecho_do_titulo_e_palavras_reordenadas_nao_e_resposta() -> None:
    assert is_echoed_title('Trilha de Cursos e Certificações', [CISCO_CONTEXT])
    assert is_echoed_title('Trilha de Cursos e Certificações da Cisco', [CISCO_CONTEXT])


def test_resposta_curta_legitima_nao_e_titulo() -> None:
    assert not is_echoed_title('15 dias úteis [1]', [PRAZO_CONTEXT])
    assert not is_echoed_title('O prazo de entrega é de 15 dias úteis [1].', [PRAZO_CONTEXT])
    assert not is_echoed_title('Ricardo [1]', ['[1]\ntitle: Ricardo Gomes\ntrecho:\nRicardo Gomes escreveu o plano.'])
    assert not is_echoed_title(
        'Porta padrão do SSH é 22 [1]',
        ['[1]\ntitle: Porta padrão do SSH\ntrecho:\n# Porta padrão do SSH\nA porta padrão do SSH é 22.'],
    )


def test_resposta_longa_que_contem_o_titulo_nao_e_copia() -> None:
    resposta = (
        'Cisco — Trilha de Cursos e Certificações oferece cursos gratuitos de redes para iniciantes e avançados.'
    )

    assert not is_echoed_title(resposta, [CISCO_CONTEXT])


def test_claim_com_frase_da_nota_nao_conta_como_titulo() -> None:
    contexto = '[1]\nsource_path: prazo.md\nclaim_extrativo: O prazo de entrega é de 15 dias úteis.\ntrecho:\nTexto.'

    assert not is_echoed_title('O prazo de entrega é de 15 dias úteis', [contexto])


def test_pergunta_devolvida_como_resposta_e_eco() -> None:
    # Medido com qchat na V3: a IA respondia com a própria pergunta, com ou sem o marcador [n].
    pergunta = 'Quantos bytes do arquivo sao usados para calcular o file_hash?'

    assert is_echoed_question(pergunta, 'Quantos bytes do arquivo sao usados para calcular o file_hash?')
    assert is_echoed_question('Para qual versao do PostgreSQL o banco sera atualizado?', 'Para qual versao do PostgreSQL o banco sera atualizado?')
    assert is_echoed_question('Qual o prazo de entrega?', 'Qual o prazo de entrega, em dias?')


def test_resposta_legitima_nao_e_eco_da_pergunta() -> None:
    # Palavra fora da pergunta ("tmpfs") ou valor novo ("30s") mostra que a resposta traz informação.
    assert not is_echoed_question('Qual tipo de volume fica em memoria e nao persiste?', 'tmpfs: em memória, não persiste')
    assert not is_echoed_question('Qual o valor do REDIS_TIMEOUT em staging?', 'O valor do REDIS_TIMEOUT em staging é 30s')
    assert not is_echoed_question(
        'Quantos registros a tabela eventos atingiu em fevereiro de 2025?',
        'A tabela eventos atingiu 180 milhões de registros em fevereiro de 2025',
    )
    assert not is_echoed_question('Quem e responsavel pelo teste em staging?', 'Rafael')
