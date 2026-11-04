import threading

from escolio.storage.vector import LocalVectorStore


def test_lojas_abertas_ao_mesmo_tempo_na_mesma_pasta_nao_quebram(tmp_path):
    # O app abre a loja em várias threads na inicialização (aquecimento, configurações, diagnóstico).
    # Sem trava, o primeiro cliente do Chroma ainda está subindo quando o segundo chega e a criação falha.
    pasta = tmp_path / 'vector_store'
    largada = threading.Barrier(6)
    erros: list[BaseException] = []

    def abrir() -> None:
        largada.wait()
        try:
            LocalVectorStore(pasta).count()
        except BaseException as exc:  # o teste quer ver qualquer falha
            erros.append(exc)

    threads = [threading.Thread(target=abrir) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert erros == []
