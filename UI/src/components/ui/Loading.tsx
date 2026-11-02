import { GroupCard, SectionHead } from './Controls';
import type { GlyphName } from './Glyph';

/** Bloco do esqueleto. A cor vem do texto do tema, então tem contraste em qualquer fundo. */
export const Sk = ({ w = '100%', h = 12, r = 6 }: { w?: number | string; h?: number; r?: number }) => (
  <span className="skeleton-box load-sk" style={{ width: w, height: h, borderRadius: r }} aria-hidden="true" />
);

/** Linhas de texto em espera. */
export const SkLines = ({ widths, h = 12, gap = 8 }: { widths: (number | string)[]; h?: number; gap?: number }) => (
  <span className="load-lines" style={{ gap }} aria-hidden="true">
    {widths.map((w, i) => {
      const key = `l${i}`;
      return <Sk key={key} w={w} h={h} />;
    })}
  </span>
);

type SkeletonCard = [GlyphName, string, string, 'wide' | 'half', (number | string)[]];

const TABS: Record<'ia' | 'voz' | 'avancado', { icon: GlyphName; title: string; lede: string; cards: SkeletonCard[] }> = {
  ia: {
    icon: 'stars',
    title: 'Fontes de IA',
    lede: 'Quem escreve a resposta a partir dos trechos das suas notas. A busca e a transcrição ficam sempre no seu computador.',
    cards: [
      ['server', 'Provedor de resposta', 'Quem transforma os trechos em resposta.', 'wide', ['34%', '58%']],
      ['cube', 'Modelo de resposta', 'Modelo que escreve a resposta.', 'half', ['100%', '58%']],
      ['link', 'Endereço do servidor', 'Vazio usa o padrão do provedor.', 'half', ['100%']],
      ['pulse', 'Conexão', '', 'wide', ['44%', '66%']],
    ],
  },
  voz: {
    icon: 'mic',
    title: 'Voz',
    lede: 'Transcrição local da pergunta falada: nada sai do seu computador.',
    cards: [
      ['wave', 'Modelo de transcrição', '', 'wide', ['40%', '72%', '28%']],
      ['globe', 'Idioma', '', 'half', ['100%']],
      ['cpu', 'Processamento', '', 'half', ['60%']],
      ['mic', 'Microfone', '', 'wide', ['100%']],
    ],
  },
  avancado: {
    icon: 'code',
    title: 'Avançado',
    lede: 'Ajustes finos de busca, trechos, indexação e resposta da IA. Mude só se souber o efeito.',
    cards: [
      ['search', 'Busca', 'Como cada pergunta encontra os trechos.', 'half', ['70%', '46%']],
      ['graph', 'Busca semântica', 'Onde o modelo de vetores roda.', 'half', ['70%', '46%']],
      ['scissors', 'Trechos', 'Como as notas são cortadas. Mudar exige reindexar.', 'half', ['70%', '46%']],
      ['layers', 'Indexação', 'Ritmo da Fila ao indexar pastas.', 'half', ['70%', '46%']],
      ['stars', 'Resposta da IA', 'Vale para Ollama, LM Studio e provedores na nuvem.', 'wide', ['60%', '40%']],
    ],
  },
};

/** Aba das Configurações antes de os ajustes chegarem: os títulos já aparecem, só os valores esperam. */
export const SettingsTabSkeleton = ({ tab }: { tab: keyof typeof TABS }) => {
  const { icon, title, lede, cards } = TABS[tab];
  return (
    <section className="settings-section" aria-busy="true" aria-label={`Carregando ${title}`}>
      <SectionHead icon={icon} title={title} lede={lede} />
      <div className="ui-grid">
        {cards.map(([cardIcon, cardTitle, desc, size, lines], i) => (
          <GroupCard key={cardTitle} icon={cardIcon} title={cardTitle} desc={desc} delay={60 + i * 60} className={size === 'wide' ? 'load-wide' : ''}>
            <div className="load-wait"><SkLines widths={lines} /></div>
          </GroupCard>
        ))}
      </div>
    </section>
  );
};

/** Fantasma do grafo: mesmo espaço do desenho, para nunca dizer "nenhuma nota" enquanto carrega. */
const NODES: [number, number, number][] = [[150, 150, 13], [240, 90, 9], [70, 90, 8], [60, 220, 9], [235, 240, 10], [150, 300, 8], [300, 170, 7], [320, 70, 4], [205, 40, 4], [120, 40, 4], [30, 50, 4], [20, 145, 4], [20, 260, 4], [90, 275, 4], [290, 290, 4], [330, 240, 4], [210, 340, 4], [110, 355, 4], [330, 130, 4], [270, 30, 4]];
const EDGES: [number, number][] = [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [0, 6], [1, 7], [1, 8], [1, 19], [2, 9], [2, 10], [3, 11], [3, 12], [3, 13], [4, 14], [4, 15], [5, 16], [5, 17], [6, 18]];

export const GraphGhost = () => (
  <div className="force-graph force-graph--ghost" role="status" aria-label="Carregando o grafo">
    <svg className="force-graph__ghost" viewBox="0 0 360 400" aria-hidden="true" focusable="false">
      {EDGES.map(([a, b]) => <line key={`${a}-${b}`} x1={NODES[a][0]} y1={NODES[a][1]} x2={NODES[b][0]} y2={NODES[b][1]} />)}
      {NODES.map(([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r} />)}
    </svg>
  </div>
);
