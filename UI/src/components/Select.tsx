/**
 * Select.tsx
 * ──────────────────────────────────────────────────────────────
 * Dropdown customizado (listbox), no lugar do <select> nativo do HTML.
 *
 * O <select> nativo não pode ser estilizado por dentro (o menu aberto
 * usa o tema do SO/WebView, destoando do tema escuro do app). Este
 * componente reimplementa o padrão ARIA de combobox+listbox com CSS
 * do próprio design system, mantendo o mesmo comportamento de teclado
 * e acessibilidade que um <select> ofereceria.
 * ──────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDownIcon } from './Icons';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
  /** Texto secundário opcional exibido junto à opção (ex.: "instalado", "230 MB") */
  hint?: string;
}

interface SelectProps {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  ariaLabel: string;
  id?: string;
  className?: string;
  disabled?: boolean;
  /** Exibido no trigger quando `value` não corresponde a nenhuma option. */
  placeholder?: string;
}

const Select = ({ value, options, onChange, ariaLabel, id, className, disabled, placeholder }: SelectProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selectedIndex = options.findIndex((option) => option.value === value);
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : null;
  const listboxId = id ? `${id}-listbox` : undefined;

  const close = useCallback(() => {
    setIsOpen(false);
    setActiveIndex(-1);
  }, []);

  // Fecha ao clicar fora ou pressionar Escape em qualquer lugar do documento.
  useEffect(() => {
    if (!isOpen) return undefined;

    const handlePointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        close();
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, close]);

  // Mantém a opção ativa visível ao navegar por teclado.
  useEffect(() => {
    if (!isOpen || activeIndex < 0) return;
    const node = listRef.current?.children[activeIndex] as HTMLElement | undefined;
    node?.scrollIntoView?.({ block: 'nearest' });
  }, [isOpen, activeIndex]);

  const nextEnabledIndex = useCallback(
    (from: number, direction: 1 | -1) => {
      if (options.length === 0) return -1;
      let index = from;
      for (let steps = 0; steps < options.length; steps += 1) {
        index = (index + direction + options.length) % options.length;
        if (!options[index]?.disabled) return index;
      }
      return -1;
    },
    [options]
  );

  const commit = useCallback(
    (index: number) => {
      const option = options[index];
      if (!option || option.disabled) return;
      onChange(option.value);
      close();
    },
    [options, onChange, close]
  );

  const open = useCallback(() => {
    if (disabled) return;
    setIsOpen(true);
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : nextEnabledIndex(-1, 1));
  }, [disabled, selectedIndex, nextEnabledIndex]);

  const handleTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (!isOpen) {
      if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault();
        open();
      }
      return;
    }
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        setActiveIndex((current) => nextEnabledIndex(current, 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        setActiveIndex((current) => nextEnabledIndex(current, -1));
        break;
      case 'Home':
        event.preventDefault();
        setActiveIndex(nextEnabledIndex(-1, 1));
        break;
      case 'End':
        event.preventDefault();
        setActiveIndex(nextEnabledIndex(0, -1));
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        commit(activeIndex);
        break;
      default:
        break;
    }
  };

  return (
    <div className={`select${className ? ` ${className}` : ''}`} ref={rootRef}>
      <button
        type="button"
        id={id}
        className="select__trigger settings-select"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={handleTriggerKeyDown}
      >
        <span className="select__trigger-label">
          {selectedOption ? selectedOption.label : placeholder ?? ''}
        </span>
        <ChevronDownIcon size={14} className="select__chevron" />
      </button>

      {isOpen && (
        <ul className="select__menu" role="listbox" id={listboxId} aria-label={ariaLabel} ref={listRef}>
          {options.map((option, index) => (
            <li
              key={option.value}
              role="option"
              aria-selected={option.value === value}
              aria-disabled={option.disabled || undefined}
              className={`select__option${index === activeIndex ? ' select__option--active' : ''}${
                option.disabled ? ' select__option--disabled' : ''
              }`}
              onMouseEnter={() => !option.disabled && setActiveIndex(index)}
              onClick={() => commit(index)}
            >
              <span className="select__option-label">{option.label}</span>
              {option.hint && <span className="select__option-hint">{option.hint}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default Select;
