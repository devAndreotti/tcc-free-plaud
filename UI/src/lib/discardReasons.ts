// Motivos do descarte da IA, em português (o código bruto fica nos detalhes técnicos). Usados no chat e no Benchmark.
const DISCARD_TEXT = new Map<string, string>([
  ['generated_no_answer_sentinel', 'A IA disse que os trechos não respondem'],
  ['generated_generic_no_answer', 'A IA disse que os trechos não respondem'],
  ['echoed_context_metadata', 'A IA repetiu o cabeçalho da nota'],
  ['unsupported_number', 'A IA citou algo que não está nos trechos'],
  ['unsupported_anchor', 'A IA citou algo que não está nos trechos'],
  ['low_claim_overlap', 'A IA escreveu longe dos trechos'],
  ['empty_generated_answer', 'A IA devolveu só [n], sem texto'],
  ['no_source_marker', 'A IA escreveu sem citar nenhum trecho'],
  ['echoed_title', 'A IA copiou um título em vez de responder'],
  ['echoed_question', 'A IA repetiu a pergunta em vez de responder'],
  ['provider_error', 'A IA falhou; mostramos o trecho'],
]);

/** Motivo em português; código que o app não conhece cai na frase genérica. */
export const discardText = (code: string | null | undefined): string =>
  (code && DISCARD_TEXT.get(code)) || 'A IA não respondeu com texto a partir dos trechos.';
