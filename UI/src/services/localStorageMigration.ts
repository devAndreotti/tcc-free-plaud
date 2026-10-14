/**
 * Lê uma chave do localStorage migrando o nome antigo (free-plaud:*) para o novo (escolio:*).
 * Se a chave nova não existe e a antiga existe, usa o valor antigo e grava na chave nova.
 * Devolve null quando nada foi salvo ou o armazenamento está bloqueado.
 */
export function readMigratedItem(key: string, legacyKey: string): string | null {
  try {
    const current = window.localStorage.getItem(key);
    if (current !== null) return current;
    const legacy = window.localStorage.getItem(legacyKey);
    if (legacy !== null) window.localStorage.setItem(key, legacy);
    return legacy;
  } catch {
    return null;
  }
}
