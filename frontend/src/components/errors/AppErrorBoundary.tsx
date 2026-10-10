import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    window.dispatchEvent(new CustomEvent("nivra:client-error", {
      detail: { name: error.name, componentStack: Boolean(info.componentStack) },
    }));
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="standalone-auth-page" role="alert">
        <section className="standalone-auth-card error-boundary-card">
          <span className="section-kicker">Recuperação segura</span>
          <h1>Não foi possível mostrar esta tela</h1>
          <p>Seus dados não foram alterados. Recarregue a página para tentar novamente.</p>
          <button className="button button-primary" onClick={() => window.location.assign("/dashboard")} type="button">
            Recarregar a Nivra
          </button>
        </section>
      </main>
    );
  }
}
