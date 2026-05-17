# 06 - Cola de Demo em 1 Minuto

## Ordem minima

### 1. Ambiente

```powershell
cd D:\Dev\Repos\Own\tcc-free-plaud
cd pipeline
uv run free-plaud doctor
```

Falar:

- backend roda sem UI
- mostra paths, SQLite e vector store

### 2. Nota canonica

```powershell
uv run free-plaud notes save "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"
```

Falar:

- documento vira nota estruturada
- sistema salva `.md` e `.meta.json`

### 3. Ask com citacao

```powershell
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md" --question "Qual e o papel do backend?"
```

Opcional vetorial:

```powershell
uv run free-plaud retrieval ask "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md" --question "Qual e o papel do backend?" --strategy vector
```

Falar:

- resposta sai estruturada
- tem `claims`, `citations` e `latency_ms`
- se faltar evidencia, o sistema pode se abster

### 4. Benchmark comparativo

```powershell
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json"
```

Falar:

- benchmark compara `lexical` vs `vector`
- hoje `lexical` ainda vence no corpus real

## Numeros para citar

- `lexical`: `MRR 0.96875`, `Recall@3 1.0`
- `vector`: `MRR 0.7916666666666666`, `Recall@3 0.9375`

## Fala pronta em 3 linhas

```text
O backend do TCC ja funciona sem interface: ele ingere documento local, gera nota canonica, responde pergunta com citacao e executa benchmark reproduzivel.

O pipeline vetorial ja esta implementado, mas no corpus real atual o baseline lexical ainda performa melhor.

O proximo passo tecnico nao e UI; e melhorar retrieval para o vetorial competir melhor com o baseline atual.
```

## Fallback

Se a suite real nao puder rodar:

```powershell
uv run free-plaud benchmark run-demo "D:\Dev\Repos\Own\tcc-free-plaud\docs\arquitetura\Arquitetura_Backend.md"
```
