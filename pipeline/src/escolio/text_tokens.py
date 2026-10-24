"""Tokenização de conteúdo e fundamentação lexical, compartilhadas por notas e benchmark.

Fica fora de `escolio.benchmark` para que o pipeline de notas (extração estruturada)
não dependa da camada de avaliação.
"""

import re
import unicodedata

_TOKEN_PATTERN = re.compile(r'[0-9A-Za-zÀ-ÖØ-öø-ÿ]+')

# Stopwords em forma normalizada (sem acento, minúsculas) para o cálculo de
# fundamentação lexical focar em palavras de conteúdo, não em conectivos.
STOPWORDS_PT = frozenset(
    {
        'a', 'ao', 'aos', 'as', 'com', 'como', 'da', 'das', 'de', 'do', 'dos',
        'e', 'em', 'entre', 'essa', 'esse', 'esta', 'este', 'eu', 'foi', 'isso',
        'ja', 'la', 'mais', 'mas', 'me', 'na', 'nao', 'nas', 'no', 'nos', 'num',
        'numa', 'o', 'os', 'ou', 'para', 'pela', 'pelo', 'por', 'que', 'se',
        'sem', 'ser', 'seu', 'sua', 'tem', 'um', 'uma', 'umas', 'uns',
    }
)


def content_tokens(text: str) -> set[str]:
    """Extrai tokens de conteúdo normalizados (sem acento, sem stopwords)."""
    tokens: set[str] = set()
    for raw in _TOKEN_PATTERN.findall(text):
        folded = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode('ascii')
        normalized = re.sub(r'[^0-9a-z]+', '', folded.lower())
        if len(normalized) < 2 or normalized in STOPWORDS_PT:
            continue
        tokens.add(normalized)
    return tokens


def lexical_groundedness(answer: str, supporting_texts: list[str]) -> float:
    """Proxy lexical de faithfulness: fração dos termos de conteúdo da resposta
    que aparecem nos trechos citados.

    Mede ancoragem, não correção: 1.0 indica que todo token informativo da
    resposta tem origem nas evidências recuperadas; valores baixos sinalizam
    afirmações sem suporte no acervo (possível alucinação). Resposta vazia
    retorna 1.0 (não há afirmação a sustentar); evidência vazia com resposta
    não vazia retorna 0.0.
    """
    answer_tokens = content_tokens(answer)
    if not answer_tokens:
        return 1.0
    support_tokens: set[str] = set()
    for text in supporting_texts:
        support_tokens |= content_tokens(text)
    if not support_tokens:
        return 0.0
    grounded = answer_tokens & support_tokens
    return len(grounded) / len(answer_tokens)
