import { useState } from "react";
import IdeaInput from "./components/IdeaInput";
import GenerateButton from "./components/GenerateButton";
import ResultPanel from "./components/ResultPanel";

/** Main sample screen: input → button → API → result. */
export default function App() {
  const [idea, setIdea] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: idea, mode: "basic" }),
      });
      if (!res.ok) throw new Error(`generate failed: ${res.status}`);
      const data = await res.json();
      setResult(data.result ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="sample-app">
      <h1>Idea Generator</h1>
      <IdeaInput value={idea} onChange={setIdea} />
      <GenerateButton disabled={busy} onClick={handleGenerate} />
      <ResultPanel result={result} error={error} />
    </main>
  );
}
