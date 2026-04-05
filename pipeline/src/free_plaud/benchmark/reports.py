from pathlib import Path


        def export_report_markdown(rows: list[dict[str, float | str]], path: Path) -> Path:
            """Exporta um relatório simples em Markdown."""
            lines = [
                '# Benchmark Report',
                '',
                '| Sample | Recall@3 |',
                '|---|---:|',
            ]
            for row in rows:
                lines.append(f"| {row['sample_id']} | {row['recall_at_3']} |")
            path.write_text('
'.join(lines) + '
', encoding='utf-8')
            return path
