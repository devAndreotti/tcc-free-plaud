import { beforeEach } from 'vitest';
import { configure } from '@testing-library/react';
import { CONVERSATIONS_STORAGE_KEY } from '../services/bridge';

// O app carrega vaults, corpus e Fila em paralelo na abertura; sob carga (suíte inteira, runner
// do CI) o findBy padrão de 1 s estoura. Teste verde continua saindo assim que o elemento aparece.
configure({ asyncUtilTimeout: 5000 });

// No navegador de teste as conversas salvas ficam no localStorage: cada teste começa sem elas.
beforeEach(() => {
  window.localStorage.removeItem(CONVERSATIONS_STORAGE_KEY);
});
