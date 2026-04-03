import { useEffect, useRef } from 'react';
import { SettingsIcon } from './Icons';

// Props do menu hambúrguer
interface HamburgerMenuProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
}

const HamburgerMenu = ({ isOpen, onClose, onOpenSettings }: HamburgerMenuProps) => {
  const menuRef = useRef<HTMLDivElement>(null);

  // Fecha ao clicar fora do menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  // Fecha ao pressionar Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Abre configurações e fecha o menu
  const handleSettingsClick = () => {
    onClose();
    onOpenSettings();
  };

  return (
    <div
      ref={menuRef}
      className="hamburger-menu"
      role="menu"
      aria-label="Menu de navegação"
    >
      {/* Item: Configurações */}
      <button
        id="menu-item-settings"
        type="button"
        className="hamburger-menu__item"
        role="menuitem"
        onClick={handleSettingsClick}
      >
        <span className="hamburger-menu__item-icon" aria-hidden="true">
          <SettingsIcon size={16} />
        </span>
        <span className="hamburger-menu__item-label">Configurações</span>
      </button>
    </div>
  );
};

export default HamburgerMenu;
