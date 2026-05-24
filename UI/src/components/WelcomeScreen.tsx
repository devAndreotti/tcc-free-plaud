// Tela de boas-vindas exibida quando não há mensagens
const WelcomeScreen = () => {
  return (
    <div className="welcome-screen" role="main" aria-label="Tela inicial do assistente">
      {/* Logo central animada */}
      <div className="welcome-screen__icon" aria-hidden="true">
        <img
          src="./brain-logo.png"
          alt="Logo Assistente IA"
          className="welcome-screen__logo-img"
        />
      </div>

      {/* Título principal */}
      <h1 className="welcome-screen__heading">
        Como posso ajudar você hoje?
      </h1>
    </div>
  );
};

export default WelcomeScreen;
