import { configure } from '@testing-library/react';

// O app carrega vaults, corpus e Fila em paralelo na abertura; sob carga (suíte inteira, runner
// do CI) o findBy padrão de 1 s estoura. Teste verde continua saindo assim que o elemento aparece.
configure({ asyncUtilTimeout: 5000 });
