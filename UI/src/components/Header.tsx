import { useState } from 'react';
import { GraphIcon, HamburgerIcon, SparkleIcon } from './Icons';
import HamburgerMenu from './HamburgerMenu';
import SettingsModal from './SettingsModal';

// Componente do cabeçalho superior da aplicação
const Header = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <>
      <header className="header" role="banner">
        {/* Lado esquerdo: botão hambúrguer + logo */}
        <div className="header__left">
          {/* Botão hambúrguer — abre o menu lateral */}
          <div className="hamburger-wrapper">
            <button
              id="btn-hamburger"
              type="button"
              className={`btn-hamburger ${isMenuOpen ? 'active' : ''}`}
              aria-label={isMenuOpen ? 'Fechar menu' : 'Abrir menu'}
              aria-expanded={isMenuOpen}
              aria-haspopup="menu"
              onClick={() => setIsMenuOpen((prev) => !prev)}
            >
              <HamburgerIcon size={20} />
            </button>

            {/* Menu dropdown */}
            <HamburgerMenu
              isOpen={isMenuOpen}
              onClose={() => setIsMenuOpen(false)}
              onOpenSettings={() => setIsSettingsOpen(true)}
            />
          </div>

          {/* Logo e nome */}
          <div className="header__brand">
            <div className="header__logo" aria-label="Assistente IA logo">
              <SparkleIcon size={18} />
            </div>
            <span className="header__title">Assistente IA</span>
          </div>
        </div>

        {/* Lado direito: botão Grafo */}
        <div className="header__actions">
          <button
            id="btn-graph"
            className="btn-graph"
            type="button"
            aria-label="Visualizar grafo de conhecimento"
          >
            <GraphIcon size={14} />
            Grafo
          </button>
        </div>
      </header>

      {/* Modal de configurações (montado fora do header para z-index correto) */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
};

export default Header;
