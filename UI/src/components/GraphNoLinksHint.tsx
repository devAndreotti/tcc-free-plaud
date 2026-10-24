// Aviso sobre o grafo no modo Links quando nenhuma nota está ligada a outra por [[...]].
// Fica sobre o painel (sem capturar o mouse) e as notas continuam desenhadas por baixo.
interface GraphNoLinksHintProps {
  noteCount: number;
}

const GraphNoLinksHint = ({ noteCount }: GraphNoLinksHintProps) => {
  const notas = noteCount === 1 ? 'nota' : 'notas';
  return (
    <div className="force-graph__hint">
      <p className="force-graph__hint-title">{`Nenhuma ligação [[…]] encontrada nas ${noteCount} ${notas}`}</p>
      <p className="force-graph__hint-tip">Use [[Nome da nota]] no Markdown para ligar notas.</p>
    </div>
  );
};

export default GraphNoLinksHint;
