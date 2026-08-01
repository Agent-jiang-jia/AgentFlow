import { Spin } from "antd";
import { lazy, Suspense } from "react";

const Workspace = lazy(() => import("./pages/Workspace"));

export default function App() {
  return (
    <Suspense
      fallback={
        <main className="app-loading">
          <Spin size="large" />
          <span>正在打开工作台…</span>
        </main>
      }
    >
      <Workspace />
    </Suspense>
  );
}
