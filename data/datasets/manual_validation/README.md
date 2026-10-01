## Datasets reais de benchmark

Estes datasets usam perguntas positivas derivadas dos arquivos em `samples/manual validetion/`.

O runner atual de benchmark opera sobre uma nota por execucao:

```powershell
uv run free-plaud benchmark run "C:\caminho\documento.md" --dataset "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\07_pdf_tecnico_estruturado.json" --strategy lexical --export
```

Regras praticas deste diretorio:

- cada arquivo JSON corresponde a um documento especifico
- as perguntas desses arquivos assumem que existe evidencia relevante no documento
- `negativas.json` traz perguntas sem resposta em nenhum documento (category `negativa`); a suite aponta para ele em `negative_dataset_path` e a comparacao mede se o chat se abstem
- `expected_terms` devem apontar para termos locais do chunk esperado, para manter o benchmark util em `lexical` e `vector`
- `suite.json` agrupa os pares documento/dataset para comparacao repetivel entre estrategias

Arquivos incluidos:

- `01_frontmatter_yaml.json`
- `02_codigo_grande_no_inicio.json`
- `03_tabela_checklist_headings.json`
- `04_ata_metadados_longos.json`
- `05_estudo_docker_fragmentado.json`
- `06_ocr_ruido_leve.json`
- `07_pdf_tecnico_estruturado.json`
- `08_pdf_problematico_contrato.json`
- `09_nota_muito_curta.json`
- `10_documento_longo_modelagem_dados.json`
- `negativas.json`
- `suite.json`

Comparacao repetivel:

```powershell
uv run free-plaud benchmark compare --suite "D:\Dev\Repos\Own\tcc-free-plaud\data\datasets\manual_validation\suite.json" --export
```
