import { useState } from 'react';
import { HamburgerIcon, FolderIcon, ZapIcon } from './Icons';
import HamburgerMenu from './HamburgerMenu';

// Props da barra lateral
interface SidebarProps {
  onOpenSettings: () => void;
  onNewTab: () => void;
  onOpenNotes: () => void;
  onOpenBenchmark: () => void;
  activeView: 'chat' | 'notes' | 'benchmark';
}

// Componente da barra lateral esquerda da aplicação
const Sidebar = ({ onOpenSettings, onNewTab, onOpenNotes, onOpenBenchmark, activeView }: SidebarProps) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

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
        {/* Botão Notes */}
        <button
          id="btn-sidebar-notes"
          type="button"
          className={`sidebar__nav-btn ${activeView === 'notes' ? 'sidebar__nav-btn--active' : ''}`}
          aria-label="Notes"
          aria-pressed={activeView === 'notes'}
          title="Notes"
          onClick={onOpenNotes}
        >
          <FolderIcon size={20} />
          <span className="sidebar__nav-label">Notes</span>
        </button>

        {/* Botão Benchmark */}
        <button
          id="btn-sidebar-benchmark"
          type="button"
          className={`sidebar__nav-btn ${activeView === 'benchmark' ? 'sidebar__nav-btn--active' : ''}`}
          aria-label="Benchmark"
          aria-pressed={activeView === 'benchmark'}
          title="Benchmark"
          onClick={onOpenBenchmark}
        >
          <ZapIcon size={20} />
          <span className="sidebar__nav-label">Benchmark</span>
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
