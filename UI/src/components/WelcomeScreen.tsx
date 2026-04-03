import { SparkleIcon } from './Icons';

// Tela de boas-vindas exibida quando não há mensagens
const WelcomeScreen = () => {
  return (
    <div className="welcome-screen" role="main" aria-label="Tela inicial do assistente">
      {/* Ícone central animado */}
      <div className="welcome-screen__icon" aria-hidden="true">
        <SparkleIcon size={32} />
      </div>

      {/* Título principal */}
      <h1 className="welcome-screen__heading">
        Como posso ajudar você hoje?
      </h1>

      {/* Subtítulo */}
      <p className="welcome-screen__subheading">
        Digite uma mensagem, anexe arquivos ou<br />
        use o microfone para começar uma conversa
      </p>
    </div>
  );
};

export default WelcomeScreen;
