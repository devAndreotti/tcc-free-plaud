import { describe, expect, it } from 'vitest';
import { describeIndexIssue, groupIndexIssues, splitIssuePath, technicalDetail } from './indexErrors';

describe('indexErrors (falhas da Fila em linguagem de usuário)', () => {
  it('traduz os códigos conhecidos e cai num genérico para os desconhecidos', () => {
    expect(describeIndexIssue('EMPTY_CONTENT').title).toBe('Nota sem conteúdo');
    expect(describeIndexIssue('EMPTY_CONTENT').actions).toEqual(['open', 'retry', 'ignore']);
    expect(describeIndexIssue('UNSUPPORTED_EXTENSION').kind).toBe('UNSUPPORTED_EXTENSION');
    expect(describeIndexIssue('AUDIO_INVALID_PCM').title).toBe('Falha ao transcrever o áudio');
    expect(describeIndexIssue('KeyError').title).toBe('Falha ao indexar');
    expect(describeIndexIssue(null).kind).toBe('UNKNOWN');
  });

  it('esconde a mensagem técnica quando ela só repete o código', () => {
    expect(technicalDetail({ source_path: 'a.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' })).toBeNull();
    expect(technicalDetail({ source_path: 'a.md', message: 'Falha X', error_code: 'INDEXING_FAILED' })).toBe('Falha X');
  });

  it('agrupa pela explicação, com erros antes de avisos', () => {
    const groups = groupIndexIssues([
      { source_path: 'a.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' },
      { source_path: 'b.pdf', message: 'PDF_PARSE_FAILED', error_code: 'PDF_PARSE_FAILED' },
      { source_path: 'c.md', message: 'EMPTY_CONTENT', error_code: 'EMPTY_CONTENT' },
    ]);
    expect(groups.map((group) => [group.info.kind, group.items.length])).toEqual([
      ['PDF_PARSE_FAILED', 1],
      ['EMPTY_CONTENT', 2],
    ]);
  });

  it('mostra o arquivo e a pasta relativa à pasta indexada', () => {
    const root = String.raw`C:\Users\ricar\Obsidian Vault\Obsidian-Core`;
    expect(splitIssuePath(String.raw`C:\Users\ricar\Obsidian Vault\Obsidian-Core\Templates\Mensal.md`, root)).toEqual({
      name: 'Mensal.md',
      folder: 'Obsidian-Core › Templates',
    });
    expect(splitIssuePath(String.raw`c:\users\ricar\obsidian vault\obsidian-core\Nota.md`, root).folder).toBe('Obsidian-Core');
    expect(splitIssuePath('D:/outro/lugar/x.md', root)).toEqual({ name: 'x.md', folder: 'D: › outro › lugar' });
  });
});
