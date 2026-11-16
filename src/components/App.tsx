import { useState } from "preact/hooks";
import { Game } from "./Game";
import { Splash } from "./Splash";

export function App() {
  const [started, setStarted] = useState(false);
  return (
    <div class="app">
      {started ? <Game /> : <Splash onStart={() => setStarted(true)} />}
    </div>
  );
}
