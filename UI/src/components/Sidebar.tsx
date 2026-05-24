import { useState } from 'react';
import { HamburgerIcon, FolderIcon, ZapIcon } from './Icons';
import HamburgerMenu from './HamburgerMenu';

// Props da barra lateral
interface SidebarProps {
  onOpenSettings: () => void;
  onNewTab: () => void;
}

// Componente da barra lateral esquerda da aplicação
const Sidebar = ({ onOpenSettings, onNewTab }: SidebarProps) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [activeItem, setActiveItem] = useState<string | null>(null);

  // Navega para a seção selecionada
  const handleNavClick = (item: string) => {
    setActiveItem((prev) => (prev === item ? null : item));
  };

  return (
    <aside className="sidebar" role="complementary" aria-label="Barra de navegação">
      {/* Logo no topo — clique abre nova conversa */}
      <button
        id="btn-new-tab"
        type="button"
        className="sidebar__logo"
        aria-label="Nova conversa"
        title="Nova conversa"
        onClick={onNewTab}
      >
        <img src="./brain-logo.png" alt="Logo Brainiac" className="sidebar__logo-img" />
      </button>

      {/* Divisor */}
      <div className="sidebar__divider" />

      {/* Navegação principal */}
      <nav className="sidebar__nav" aria-label="Navegação principal">
        {/* Botão Pastas */}
        <button
          id="btn-sidebar-pastas"
          type="button"
          className={`sidebar__nav-btn ${activeItem === 'pastas' ? 'sidebar__nav-btn--active' : ''}`}
          aria-label="Pastas"
          aria-pressed={activeItem === 'pastas'}
          title="Pastas"
          onClick={() => handleNavClick('pastas')}
        >
          <FolderIcon size={20} />
          <span className="sidebar__nav-label">Pastas</span>
        </button>

        {/* Botão Skills */}
        <button
          id="btn-sidebar-skills"
          type="button"
          className={`sidebar__nav-btn ${activeItem === 'skills' ? 'sidebar__nav-btn--active' : ''}`}
          aria-label="Skills"
          aria-pressed={activeItem === 'skills'}
          title="Skills"
          onClick={() => handleNavClick('skills')}
        >
          <ZapIcon size={20} />
          <span className="sidebar__nav-label">Skills</span>
        </button>
      </nav>

      {/* Espaço flexível que empurra o hambúrguer para a base */}
      <div className="sidebar__spacer" />

      {/* Hambúrguer na base da sidebar */}
      <div className="sidebar__hamburger-wrapper">
        <button
          id="btn-hamburger"
          type="button"
          className={`sidebar__hamburger ${isMenuOpen ? 'active' : ''}`}
          aria-label={isMenuOpen ? 'Fechar menu' : 'Abrir menu'}
          aria-expanded={isMenuOpen}
          aria-haspopup="menu"
          title="Menu"
          onClick={() => setIsMenuOpen((prev) => !prev)}
        >
          <HamburgerIcon size={20} />
        </button>

        {/* Dropdown do hambúrguer — abre para cima */}
        <HamburgerMenu
          isOpen={isMenuOpen}
          onClose={() => setIsMenuOpen(false)}
          onOpenSettings={onOpenSettings}
        />
      </div>
    </aside>
  );
};

export default Sidebar;
