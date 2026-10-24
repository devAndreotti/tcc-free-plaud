"""Faithfulness semântica com juiz LLM. Offline e opcional: fica fora do gate do CI.

Método inspirado no RAGAS (Es et al., 2023, "RAGAS: Automated Evaluation of
Retrieval Augmented Generation", arXiv:2309.15217): a resposta é decomposta em
afirmações e cada afirmação é verificada contra os trechos que ela cita. A
implementação é própria, sem o pacote ragas nem outra dependência: só a
stdlib e o mesmo transporte HTTP do provider openai-compatible.
"""

import json
import re
import unicodedata
from collections.abc import Callable
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel

from escolio.benchmark.metrics import bootstrap_ci
from escolio.benchmark.runners import BenchmarkComparisonResult
from escolio.providers.answer import (
    INVALID_BASE_URL_ERROR,
    AnswerProviderError,
    _extract_answer_text,
    _is_http_base_url,
    _transport_error,
)

PROMPT_VERSION = 'faithfulness-pt-v1'
Verdict = Literal['suportado', 'nao_suportado', 'indeterminado']
JudgeFn = Callable[[str], str]

JUDGE_INSTRUCTION = (
    'Voce verifica se uma AFIRMACAO e sustentada pelos TRECHOS, em portugues brasileiro. '
    'Marque SUPORTADO somente se os TRECHOS dizem a AFIRMACAO ou permitem conclui-la diretamente, '
    'sem conhecimento externo. Numeros, nomes e termos tecnicos precisam aparecer nos TRECHOS. '
    'Em qualquer outro caso, marque NAO_SUPORTADO. '
    'Responda somente com uma palavra: SUPORTADO ou NAO_SUPORTADO.'
)
# Aceita NAO_SUPORTADO, "NAO SUPORTADO", "não é suportado" e formas no feminino, após normalizar acentos e caixa.
_VERDICT_PATTERN = re.compile(r'\b(NAO(?:[\s_-]+(?:E|FOI|SER))?[\s_-]*SUPORTAD[OA]|SUPORTAD[OA])\b')
_CITATION_MARKER = re.compile(r'\[\s*\d+(?:\s*[,;]\s*\d+)*\s*\]')
_SENTENCE_BREAK = re.compile(r'(?<=[.!?])\s+|\n+')
_SPACE_BEFORE_PUNCT = re.compile(r'\s+([.,;:!?])')


class ClaimVerdict(BaseModel):
    claim: str
    verdict: Verdict


class AnswerFaithfulness(BaseModel):
    sample_id: str
    question: str
    score: float
    claims: list[ClaimVerdict]


class StrategyFaithfulness(BaseModel):
    strategy: str
    answer_count: int
    claim_count: int
    supported_count: int
    # Veredito que não pôde ser lido do juiz; conta como não suportado.
    unparsed_count: int
    # bootstrap percentil por resposta: mean, lower, upper, confidence. None sem respostas.
    faithfulness: dict[str, float] | None = None
    answers: list[AnswerFaithfulness]


class FaithfulnessReport(BaseModel):
    source_comparison_id: str
    suite_name: str
    judge_model: str
    judge_base_url: str
    prompt_version: str = PROMPT_VERSION
    strategies: dict[str, StrategyFaithfulness]


def split_claims(answer: str) -> list[str]:
    """Quebra a resposta em afirmações (uma por sentença), sem os marcadores [n]. Determinístico."""
    sem_marcadores = _CITATION_MARKER.sub('', answer)
    claims: list[str] = []
    for trecho in _SENTENCE_BREAK.split(sem_marcadores):
        frase = _SPACE_BEFORE_PUNCT.sub(r'\1', re.sub(r'\s+', ' ', trecho)).strip()
        if re.search(r'[0-9A-Za-zÀ-ÿ]', frase):
            claims.append(frase)
    return claims


def build_judge_prompt(claim: str, contexts: list[str]) -> str:
    trechos = '\n\n'.join(f'[{numero}] {texto}' for numero, texto in enumerate(contexts, start=1))
    return f'{JUDGE_INSTRUCTION}\n\nTRECHOS:\n{trechos}\n\nAFIRMACAO:\n{claim}\n\nVeredito:'


def parse_verdict(texto: str) -> Verdict | None:
    """Lê o veredito do juiz tolerando caixa, acentos, markdown e texto em volta.

    Se o juiz repetir as opções, vale a última ocorrência (é a que ele escolheu).
    Sem nenhum veredito reconhecível, devolve None.
    """
    normalizado = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').upper()
    achados = _VERDICT_PATTERN.findall(normalizado)
    if not achados:
        return None
    return 'nao_suportado' if achados[-1].startswith('NAO') else 'suportado'


def _verdict(claim: str, trechos: list[str], judge: JudgeFn) -> Verdict:
    if not trechos:  # sem evidência nenhuma, a afirmação não tem como estar sustentada
        return 'nao_suportado'
    return parse_verdict(judge(build_judge_prompt(claim, trechos))) or 'indeterminado'


def judge_claim(claim: str, contexts: list[str], judge: JudgeFn) -> bool:
    """True quando o juiz marca a afirmação como SUPORTADA pelos contextos."""
    return _verdict(claim, [texto for texto in contexts if texto.strip()], judge) == 'suportado'


def verify_claims(answer: str, contexts: list[str], judge: JudgeFn) -> list[ClaimVerdict]:
    trechos = [texto for texto in contexts if texto.strip()]
    return [ClaimVerdict(claim=claim, verdict=_verdict(claim, trechos, judge)) for claim in split_claims(answer)]


def _score(verdicts: list[ClaimVerdict]) -> float:
    if not verdicts:
        return 1.0
    return sum(item.verdict == 'suportado' for item in verdicts) / len(verdicts)


def faithfulness_score(answer: str, contexts: list[str], judge: JudgeFn) -> float:
    """Fração das afirmações da resposta que o juiz marca como suportadas.

    Resposta sem afirmações retorna 1.0 e evidência vazia com afirmações retorna 0.0, como
    `lexical_groundedness`. Veredito ilegível conta como não suportado.
    """
    return _score(verify_claims(answer, contexts, judge))


def make_openai_compatible_judge(
    base_url: str,
    model: str,
    api_key: str | None = None,
    timeout: int = 120,
) -> JudgeFn:
    """Juiz via /chat/completions com temperatura 0, no mesmo padrão HTTP do provider de resposta."""
    if not _is_http_base_url(base_url):
        raise AnswerProviderError(INVALID_BASE_URL_ERROR)
    endpoint = f'{base_url.rstrip("/")}/chat/completions'
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    def judge(prompt: str) -> str:
        payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0}
        request = Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise _transport_error(exc) from exc
        try:
            text, _, _ = _extract_answer_text(json.loads(body.decode('utf-8')))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AnswerProviderError('Provider retornou payload invalido.') from exc
        return text

    return judge


def build_faithfulness_report(
    comparison: BenchmarkComparisonResult,
    judge: JudgeFn,
    *,
    judge_model: str,
    judge_base_url: str,
) -> FaithfulnessReport:
    """Julga cada resposta do chat (todas as estratégias da passada no corpus) e agrega com bootstrap."""
    if comparison.corpus is None:
        raise ValueError('O JSON não tem a passada no corpus; gere-o com `benchmark compare`.')
    strategies: dict[str, StrategyFaithfulness] = {}
    for strategy, linhas in comparison.corpus.queries.items():
        faltando = [linha.sample_id for linha in linhas if linha.answered and linha.answer is None]
        if faltando:
            raise ValueError(
                f'{len(faltando)} respostas sem texto ou trechos em `{strategy}`. '
                'Gere o JSON com `benchmark compare --registrar-respostas`.'
            )
        answers: list[AnswerFaithfulness] = []
        for linha in linhas:
            if not (linha.answered and linha.answer):
                continue
            claims = verify_claims(linha.answer, linha.contexts or [], judge)  # uma chamada de juiz por afirmação
            answers.append(
                AnswerFaithfulness(sample_id=linha.sample_id, question=linha.question, score=_score(claims), claims=claims)
            )
        all_claims = [claim for answer in answers for claim in answer.claims]
        strategies[strategy] = StrategyFaithfulness(
            strategy=strategy,
            answer_count=len(answers),
            claim_count=len(all_claims),
            supported_count=sum(claim.verdict == 'suportado' for claim in all_claims),
            unparsed_count=sum(claim.verdict == 'indeterminado' for claim in all_claims),
            faithfulness=bootstrap_ci([answer.score for answer in answers]) if answers else None,
            answers=answers,
        )
    return FaithfulnessReport(
        source_comparison_id=comparison.comparison_id,
        suite_name=comparison.suite_name,
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        strategies=strategies,
    )
