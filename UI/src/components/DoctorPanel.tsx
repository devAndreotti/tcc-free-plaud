import { Sk, SkLines } from './ui/Loading';
import type { ReactNode } from 'react';
import type { DoctorReport } from '../services/bridge';
import { checkLabel, groupChecks } from '../lib/doctorChecks';
import { Glyph, type GlyphName } from './ui/Glyph';
import { GroupCard, SectionHead } from './ui/Controls';

const GROUP_ICONS: Record<string, GlyphName> = { indice: 'db', ia: 'stars', voz: 'mic', outros: 'sliders' };
const GROUP_DESC: Record<string, string> = { indice: 'Banco, vetores e busca.', ia: 'Quem escreve a resposta.', voz: 'Transcrição local.', outros: 'Pastas e permissões.' };
const C = 2 * Math.PI * 20;

/** Anel com a parte ok, de aviso e de erro do diagnóstico; os arcos crescem com transição. */
const DoctorRing = ({ doctor, running }: { doctor: DoctorReport; running: boolean }) => {
  const total = doctor.ok_count + doctor.warning_count + doctor.error_count || 1;
  const gap = 2.5;
  const arc = (count: number) => Math.max(0, (count / total) * C - (count ? gap : 0));
  const ok = arc(doctor.ok_count);
  const warn = arc(doctor.warning_count);
  const err = arc(doctor.error_count);
  return (
    <svg className={`doctor-ring${running ? ' ui-spin ui-spin--slow' : ''}`} width="54" height="54" viewBox="0 0 52 52" role="img" aria-label={`${doctor.ok_count} de ${total} verificações ok`}>
      <circle cx="26" cy="26" r="20" fill="none" stroke="var(--border-color)" strokeWidth="6" />
      <circle className="doctor-ring__arc" cx="26" cy="26" r="20" fill="none" stroke="var(--ok)" strokeWidth="6" strokeLinecap="round" strokeDasharray={`${ok} ${C}`} transform="rotate(-90 26 26)" />
      <circle className="doctor-ring__arc" cx="26" cy="26" r="20" fill="none" stroke="var(--warn)" strokeWidth="6" strokeLinecap="round" strokeDasharray={`${warn} ${C}`} strokeDashoffset={-(ok + gap)} transform="rotate(-90 26 26)" />
      <circle className="doctor-ring__arc" cx="26" cy="26" r="20" fill="none" stroke="var(--err)" strokeWidth="6" strokeLinecap="round" strokeDasharray={`${err} ${C}`} strokeDashoffset={-(ok + warn + gap * 2)} transform="rotate(-90 26 26)" />
      {!running && <text x="26" y="30" textAnchor="middle" fontSize="11" fontWeight="600" fontFamily="var(--font-mono)" fill="var(--text-primary)">{doctor.ok_count}/{total}</text>}
    </svg>
  );
};

interface DoctorPanelProps {
  title: ReactNode;
  doctor: DoctorReport;
  stats: { notes: number; sqlite: number; vectors: number };
  running: boolean;
  onRerun: () => void;
}

/** Diagnóstico antes de chegar: resumo, contagens e grupos já no lugar. */
export const DoctorSkeleton = () => (
  <div className="load-wait" role="status" aria-label="Carregando diagnóstico" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
    <div className="ui-card rise load-row" style={{ padding: '14px 18px' }}><Sk w={52} h={52} r={26} /><SkLines widths={['34%', '52%']} /></div>
    <div className="doctor__stats">
      {[0, 1, 2].map((key) => (
        <div key={key} className="doctor__stat rise load-row" style={{ animationDelay: `${60 + key * 50}ms` }}><Sk w={36} h={36} r={11} /><SkLines widths={['60%', '38%', '70%']} gap={6} /></div>
      ))}
    </div>
    {[5, 2, 2].map((rows, group) => {
      const key = `g${group}`;
      return (
        <div key={key} className="ui-card rise" style={{ padding: '14px 18px', animationDelay: `${160 + group * 60}ms` }}>
          <SkLines widths={Array.from({ length: rows }, (_, i) => `${72 - i * 6}%`)} gap={12} />
        </div>
      );
    })}
  </div>
);

const DoctorPanel = ({ title, doctor, stats, running, onRerun }: DoctorPanelProps) => {
  const total = doctor.ok_count + doctor.warning_count + doctor.error_count;
  const headline = running
    ? 'Verificando…'
    : doctor.error_count > 0
      ? `${doctor.error_count} ${doctor.error_count === 1 ? 'verificação com erro' : 'verificações com erro'}`
      : doctor.warning_count > 0
        ? `${doctor.warning_count} ${doctor.warning_count === 1 ? 'aviso' : 'avisos'}`
        : 'Tudo certo';
  const groups = groupChecks(doctor.checks);
  // Uma chave por resultado: ao verificar de novo, as linhas entram de novo em sequência.
  const runKey = `${doctor.latency_ms}-${doctor.ok_count}-${doctor.error_count}`;
  let row = 0;

  const renderGroup = (group: (typeof groups)[number], i: number) => {
    const bad = group.checks.filter((check) => check.status !== 'ok').length;
    return (
      <GroupCard
        key={group.id}
        icon={GROUP_ICONS[group.id] ?? 'sliders'}
        title={group.title}
        desc={GROUP_DESC[group.id]}
        delay={160 + i * 60}
        right={
          bad > 0 ? (
            <span className={`pill ${group.checks.some((c) => c.status === 'error') ? 'pill--err' : 'pill--warn'}`}>{bad === 1 ? '1 a ver' : `${bad} a ver`}</span>
          ) : (
            <span className="pill pill--ok">{group.checks.length} de {group.checks.length} ok</span>
          )
        }
      >
        <ul className="doctor__checks" key={runKey}>
          {group.checks.map((check) => (
            <li key={check.code} className={`doctor__check doctor__check--${check.status} rise`} style={{ animationDelay: `${(row++) * 70}ms` }}>
              <Glyph name={check.status === 'ok' ? 'checkCircle' : check.status === 'warning' ? 'shield' : 'xCircle'} size={16} />
              <div>
                <span className="doctor__label">{checkLabel(check.code)}</span>
                <span className="doctor__msg">{check.message}</span>
                {check.action && check.status !== 'ok' && <span className="doctor__action">{check.action}</span>}
              </div>
              <span className="doctor__meta mono">{check.latency_ms != null && check.latency_ms >= 100 ? `${check.code} · ${check.latency_ms} ms` : check.code}</span>
            </li>
          ))}
        </ul>
      </GroupCard>
    );
  };

  return (
    <section className="settings-section doctor" aria-labelledby="settings-doctor">
      <SectionHead icon="pulse" id="settings-doctor" title={title} lede="Confere índice, IA e voz da vault ativa." />
      <div className={`doctor__summary doctor__summary--${running ? 'running' : doctor.status} rise`}>
        <DoctorRing doctor={doctor} running={running} />
        <div>
          <b>{headline}</b>
          <span className="doctor__summary-meta">
            {total} {total === 1 ? 'verificação' : 'verificações'} · {doctor.latency_ms} ms
          </span>
        </div>
        <button type="button" className="btn ui-press" onClick={onRerun} disabled={running}>
          <span className={running ? 'ui-spin' : undefined} style={{ display: 'inline-flex' }}><Glyph name="refresh" size={14} /></span>
          {running ? 'Verificando…' : 'Verificar de novo'}
        </button>
      </div>
      <dl className="doctor__stats">
        {[
          ['notes', 'Notas', stats.notes, 'em todas as pastas'],
          ['db', 'Trechos no SQLite', stats.sqlite, 'busca por palavras'],
          ['graph', 'Vetores no Chroma', stats.vectors, stats.vectors === stats.sqlite ? 'batem com o SQLite' : 'diferente do SQLite'],
        ].map(([icon, label, value, sub], i) => (
          <div key={label as string} className="doctor__stat rise lift" style={{ animationDelay: `${60 + i * 50}ms` }}>
            <span className="glyph-badge" style={{ width: 36, height: 36, borderRadius: 11 }} aria-hidden="true"><Glyph name={icon as GlyphName} size={18} /></span>
            <div>
              <dt>{label as string}</dt>
              <dd className="mono">{(value as number).toLocaleString('pt-BR')}</dd>
              <small>{sub as string}</small>
            </div>
          </div>
        ))}
      </dl>
      <div className="doctor__groups">
        {groups.length > 0 && renderGroup(groups[0], 0)}
        <div className="doctor__groups-side">{groups.slice(1).map((group, i) => renderGroup(group, i + 1))}</div>
      </div>
    </section>
  );
};

export default DoctorPanel;
