/**
 * Markdown em texto de leitura, só para exibição (o dado do trecho não muda).
 * Tira `#` de títulos, `**`/`__`/`*` de ênfase, a sintaxe de links, imagens, crases e cercas de código,
 * e a linha `|---|` das tabelas. Listas e o resto do texto ficam como estão.
 * Tudo é varredura linear: cada marcador olha só até o próximo par (ou até um limite fixo),
 * sem regex com retrocesso (a nota pode vir de terceiros; ver 77ea26d).
 */

const LINK_TEXT_MAX = 300;
const LINK_URL_MAX = 2000;

const isSpace = (c: string | undefined) => c === undefined || c === ' ' || c === '\t';
const isWord = (c: string | undefined) => c !== undefined && /[\p{L}\p{N}]/u.test(c);

/** `[texto](url)` em `i` (o `[`): devolve o texto e onde a sintaxe termina, ou null. */
function parseLink(line: string, i: number): { text: string; end: number } | null {
  const stop = Math.min(line.length, i + 1 + LINK_TEXT_MAX);
  let close = -1;
  for (let k = i + 1; k < stop; k++) {
    if (line[k] === ']') { close = k; break; }
  }
  if (close < 0 || line[close + 1] !== '(') return null;
  const urlStop = Math.min(line.length, close + 2 + LINK_URL_MAX);
  for (let k = close + 2; k < urlStop; k++) {
    const c = line[k];
    if (c === ')') return { text: line.slice(i + 1, close), end: k + 1 };
    if (c === ' ' || c === '\t') return null;
  }
  return null;
}

function inline(line: string): string {
  let out = '';
  const dropAt = new Set<number>(); // posições de fechamento já decididas
  let i = 0;
  while (i < line.length) {
    const c = line[i];
    if (dropAt.has(i)) { i += c === line[i + 1] ? 2 : 1; continue; }
    if (c === '`') {
      const j = line.indexOf('`', i + 1);
      if (j > i + 1) { out += line.slice(i + 1, j); i = j + 1; continue; }
    } else if (c === '!' && line[i + 1] === '[') {
      const link = parseLink(line, i + 1);
      if (link) { out += link.text; i = link.end; continue; }
    } else if (c === '[') {
      const link = parseLink(line, i);
      if (link) { out += link.text; i = link.end; continue; }
    } else if ((c === '*' || c === '_') && line[i + 1] === c) {
      // **negrito** e __negrito__: o fechamento é o par mais próximo.
      const j = line.indexOf(c + c, i + 2);
      if (j > i + 2 && !isSpace(line[i + 2]) && !isSpace(line[j - 1]) && !(c === '_' && (isWord(line[i - 1]) || isWord(line[j + 2])))) {
        dropAt.add(j);
        i += 2;
        continue;
      }
    } else if (c === '*') {
      // *ênfase*: abre antes de não-espaço e fecha depois de não-espaço; "2 * 3 * 4" fica como está.
      const j = line.indexOf('*', i + 1);
      if (j > i + 1 && line[j + 1] !== '*' && !isSpace(line[i + 1]) && !isSpace(line[j - 1])) {
        dropAt.add(j);
        i += 1;
        continue;
      }
    }
    out += c;
    i += 1;
  }
  return out;
}

const isTableRule = (trimmed: string) => {
  if (!trimmed.includes('|') || !trimmed.includes('--')) return false;
  for (const c of trimmed) if (c !== '|' && c !== '-' && c !== ':' && c !== ' ' && c !== '\t') return false;
  return true;
};

function heading(line: string): string | null {
  let p = 0;
  while (p < 3 && line[p] === ' ') p++;
  let n = 0;
  while (line[p + n] === '#') n++;
  if (n < 1 || n > 6 || !(p + n === line.length || isSpace(line[p + n]))) return null;
  let rest = line.slice(p + n).trim();
  let e = rest.length;
  while (e > 0 && rest[e - 1] === '#') e--;
  if (e < rest.length && (e === 0 || rest[e - 1] === ' ')) rest = rest.slice(0, e).trimEnd();
  return rest;
}

export function plainMarkdown(text: string): string {
  const lines = text.split('\n');
  const out: string[] = [];
  let fence = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('```') || trimmed.startsWith('~~~')) { fence = !fence; continue; }
    if (fence) { out.push(line); continue; }
    if (isTableRule(trimmed)) continue;
    const title = heading(line);
    if (title !== null) { out.push(inline(title)); continue; }
    if (trimmed.startsWith('|')) {
      const cells = trimmed.split('|').map((cell) => cell.trim());
      if (cells[0] === '') cells.shift();
      if (cells[cells.length - 1] === '') cells.pop();
      out.push(inline(cells.join(' · ')));
      continue;
    }
    out.push(inline(line));
  }
  return out.join('\n');
}
