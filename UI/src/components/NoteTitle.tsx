import { iconBody, titleParts, useNoteIconsMode, type NoteIconsMode } from '../lib/noteIcons';

interface NoteTitleProps {
  text: string;
  /** Força um modo (a prévia em Aparência mostra os três lado a lado). */
  mode?: NoteIconsMode;
}

/** Título de nota com o emoji como a Aparência pede: SVG na cor do texto, original ou sem nada. */
export const NoteTitle = ({ text, mode }: NoteTitleProps) => {
  const current = useNoteIconsMode();
  return (
    <>
      {titleParts(text, mode ?? current).map((part, i) => {
        if (typeof part === 'string') return part;
        const body = iconBody(part.key);
        if (!body) return null;
        return (
          <svg
            key={`${part.key}${i}`}
            className="note-icon"
            viewBox="0 0 32 32"
            role="img"
            aria-label={part.emoji}
            // Vem só de assets/emoji-svg.json, nunca do conteúdo da nota.
            dangerouslySetInnerHTML={{ __html: body }}
          />
        );
      })}
    </>
  );
};
