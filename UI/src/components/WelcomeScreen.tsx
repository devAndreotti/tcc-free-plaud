// Tela inicial exibida quando a conversa ainda não tem mensagens
const WelcomeScreen = () => (
  <div className="welcome" role="main" aria-label="Tela inicial">
    <span className="welcome__mark" aria-hidden="true">ES</span>
    <h1 className="welcome__title">Pergunte ao seu vault</h1>
    <p className="welcome__lede">
      As respostas vêm só das notas indexadas, e cada afirmação aponta para o trecho que a sustenta.
    </p>
  </div>
);

export default WelcomeScreen;
