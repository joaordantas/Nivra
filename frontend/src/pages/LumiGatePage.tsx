import { useEffect, useState } from "react";

import { ComingSoonPage } from "./ComingSoonPage";
import { LumiPage } from "./LumiPage";
import { api } from "../services/api";

export function LumiGatePage() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let mounted = true;
    api.getLumiCapabilities()
      .then((capabilities) => {
        if (mounted) setEnabled(capabilities.public_enabled === true);
      })
      .catch(() => {
        if (mounted) setEnabled(false);
      });
    return () => { mounted = false; };
  }, []);

  if (enabled) return <LumiPage />;
  return (
    <ComingSoonPage
      title="Lumi"
      description="A assistente financeira da Nivra está em desenvolvimento. As ações financeiras ainda não estão disponíveis nesta versão."
    />
  );
}
