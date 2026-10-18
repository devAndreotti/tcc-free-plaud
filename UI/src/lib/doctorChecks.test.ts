import { describe, expect, it } from 'vitest';
import type { DoctorCheck } from '../services/bridge';
import { checkLabel, groupChecks } from './doctorChecks';

const check = (code: string, status: DoctorCheck['status']): DoctorCheck => ({
  code,
  status,
  message: '',
  action: null,
  latency_ms: null,
  details: {},
});

describe('checkLabel', () => {
  it('traduz códigos conhecidos', () => {
    expect(checkLabel('sqlite')).toBe('Banco de notas (SQLite)');
    expect(checkLabel('audio.device')).toBe('Dispositivo da transcrição');
    expect(checkLabel('audio.runtime')).toBe('Diagnóstico de áudio');
  });

  it('devolve o próprio código quando não conhece', () => {
    expect(checkLabel('codigo.novo')).toBe('codigo.novo');
    expect(checkLabel('constructor')).toBe('constructor');
  });
});

describe('groupChecks', () => {
  it('agrupa em Índice, IA, Voz e Outros, nessa ordem, e omite grupos vazios', () => {
    const groups = groupChecks([
      check('audio.models', 'ok'),
      check('codigo.novo', 'ok'),
      check('api_key', 'ok'),
      check('settings.embedding_model', 'ok'),
    ]);

    expect(groups.map((group) => [group.id, group.title])).toEqual([
      ['indice', 'Índice'],
      ['ia', 'IA'],
      ['voz', 'Voz'],
      ['outros', 'Outros'],
    ]);
    expect(groupChecks([check('sqlite', 'ok')]).map((group) => group.id)).toEqual(['indice']);
  });

  it('põe erro antes de aviso e aviso antes de ok, mantendo a ordem entre iguais', () => {
    const [indice] = groupChecks([
      check('sqlite', 'ok'),
      check('fts', 'warning'),
      check('chroma', 'error'),
      check('corpus', 'ok'),
    ]);

    expect(indice.checks.map((c) => c.code)).toEqual(['chroma', 'fts', 'sqlite', 'corpus']);
  });
});
