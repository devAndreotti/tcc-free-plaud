from escolio.app.doctor_models import DoctorReport


def doctor_report_lines(report: DoctorReport) -> list[str]:
    lines = [
        f'status: {report.status}',
        f'checks: ok={report.ok_count} warning={report.warning_count} error={report.error_count}',
        f'latencia_ms: {report.latency_ms}',
        '',
    ]
    for check in report.checks:
        lines.append(f'- {check.code}: {check.status} - {check.message}')
        if check.action:
            lines.append(f'  acao: {check.action}')
        if check.latency_ms is not None:
            lines.append(f'  latencia_ms: {check.latency_ms}')
    return lines


def doctor_report_text(report: DoctorReport) -> str:
    return '\n'.join(doctor_report_lines(report))
