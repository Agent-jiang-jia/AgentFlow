import "antd/dist/reset.css";
import "./styles.css";

import { ConfigProvider } from "antd";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Root element was not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#235f51",
          borderRadius: 12,
          fontFamily:
            '"Segoe UI", "Microsoft YaHei", system-ui, -apple-system, sans-serif',
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
);

