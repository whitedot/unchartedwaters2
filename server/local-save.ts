import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createInterface } from "node:readline";
import type { Plugin } from "vite";

// Give each dev/preview process its own loopback port, sharing the project's save.
export function localSave(): Plugin {
  return {
    name: "local-game-save",
    apply: "serve",
    async config() {
      const dir = resolve(process.env.WATER2_SAVE_DIR || ".game/saves");
      mkdirSync(dir, { recursive: true, mode: 0o700 });
      const php = spawn("php", ["-S", "127.0.0.1:0", "server/save.php"], {
        env: { ...process.env, WATER2_SAVE_DIR: dir },
        stdio: ["ignore", "ignore", "pipe"],
      });
      process.once("exit", () => php.kill());
      const target = await new Promise<string>((ready, fail) => {
        php.once("error", fail);
        php.once("exit", code => fail(new Error("PHP save server exited: " + code)));
        createInterface({ input: php.stderr }).on("line", line => {
          const address = line.match(/http:\/\/127\.0\.0\.1:\d+/);
          if (address) ready(address[0]);
        });
      });
      const proxy = { "^/api/save$": target };
      return { server: { proxy }, preview: { proxy } };
    },
  };
}
