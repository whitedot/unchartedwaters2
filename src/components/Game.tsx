import nipple from "nipplejs";
import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { createDos } from "../dos/create-dos";
import {
  EventHandler,
  blockAddEventListener,
  createKeyboardEvent,
  getBlockedHandler,
  restoreAddEventListener,
} from "../event";
import { readLegacySave } from "../fs/create-idb-file-system";
import { openServerSave } from "../fs/server-save";
import { arrowKeypadCode } from "../arrow-keys";
import { detectFileChange } from "../fs/detect-file-change";
import { VirtualKeyboard } from "./VirtualKeyboard.tsx";

const JOYSTICK_MAPS = [
  105, // ArrowRightUp
  104, // ArrowUp
  103, // ArrowLeftUp
  100, // ArrowLeft
  97, // ArrowLeftDown
  98, // ArrowDown
  99, // ArrowRightDown
  102, // ArrowRight
];

const KEY_ALIAS: Record<string, number> = {
  KeyR: 107, // +
  KeyE: 109, // -
  KeyW: 106, // *
  KeyQ: 111, // /

  // Tenkeyless diagonal (UIO/JKL/M,. → Numpad 789/456/123)
  KeyU: 103, // Numpad7 (LeftUp)
  KeyI: 104, // Numpad8 (Up)
  KeyO: 105, // Numpad9 (RightUp)
  KeyJ: 100, // Numpad4 (Left)
  KeyK: 101, // Numpad5 (Center)
  KeyL: 102, // Numpad6 (Right)
  KeyM: 97, // Numpad1 (LeftDown)
  Comma: 98, // Numpad2 (Down)
  Period: 99, // Numpad3 (RightDown)

  // Special
  ArrowLeftDown: 97,
  ArrowRightDown: 99,
  ArrowLeftUp: 103,
  ArrowRightUp: 105,

  Enter: 13, // NumpadEnter
  ArrowLeft: 100, // Numpad4
  ArrowUp: 104, // Numpad8
  ArrowRight: 102, // Numpad6
  ArrowDown: 98, // Numpad2
};

function blockGameMouse(event: MouseEvent) {
  if (event instanceof PointerEvent && event.pointerType !== "mouse") return;
  event.preventDefault();
  event.stopPropagation();
}

// Towns accept cardinal keypad digits. Diagonal keypad shortcuts use their
// vertical component, while overlapping arrow keys use the most recent press.
const townKeys: Record<number, string> = {
  97: "2", 98: "2", 99: "2", 100: "4", 102: "6", 103: "8", 104: "8", 105: "8",
};

const saveFile = "KOUKAI2.DAT";

export function Game() {
  const [width, setWidth] = useState(640);
  const [height, setHeight] = useState(480);

  const [joystickCode, setJoystickCode] = useState<number | null>(null);
  const joystickCodeBefore = useRef<number | null>(null);

  const [error, setError] = useState("");
  const walkKeys = useRef(new Map<string | number, string>());
  const writeWalkKey = useRef<(digit: string) => void>(() => {});
  const heldArrows = useRef(new Set<string>());
  const [enabledToggleFullscreen, setEnabledToggleFullscreen] = useState(false);
  const [enabledToggleKeyboard, setEnabledToggleKeyboard] = useState(
    () => !window.matchMedia("(pointer: fine)").matches,
  );

  const screen = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const mobileController = useRef<HTMLDivElement>(null);

  const keydownHandlers = useRef<EventHandler[]>([]);
  const keyupHandlers = useRef<EventHandler[]>([]);

  const [toastMessage, setToastMessage] = useState<string | undefined>();
  const [innerToastMessage, setInnerToastMessage] = useState<
    string | undefined
  >();

  useEffect(() => {
    if (toastMessage) {
      setInnerToastMessage(toastMessage);
      const timeout = setTimeout(() => {
        setToastMessage(undefined);
      }, 3000);
      return () => clearTimeout(timeout);
    }
  }, [toastMessage]);



  const handleResize = useCallback(() => {
    const { width: screenWidth, height: screenHeight } =
      screen.current!.getBoundingClientRect();
    if (screenWidth / 640 > screenHeight / 480) {
      setWidth(~~((screenHeight * 640) / 480));
      setHeight(screenHeight);
    } else {
      setWidth(screenWidth);
      setHeight(~~((screenWidth * 480) / 640));
    }
  }, []);

  const handleBeforeUnload = useCallback((e: BeforeUnloadEvent) => {
    e.preventDefault();
    return (e.returnValue =
      "페이지를 벗어나면 저장하지 않은 내용이 날아갈 수 있습니다.");
  }, []);

  const handleFullScreenChange = useCallback(() => {
    setEnabledToggleFullscreen(!!window.document.fullscreenElement);
  }, []);

  const trackWalkKey = useCallback((id: string | number, code: number, down: boolean) => {
    const digit = townKeys[code];
    if (!digit) return;
    const held = walkKeys.current;
    if (down === held.has(id)) return;
    if (down) held.set(id, digit);
    else held.delete(id);
    const digits = Array.from(held.values());
    writeWalkKey.current(digits[digits.length - 1] || "");
  }, []);

  const handleKeyDown = useCallback((code: number, track = true) => {
    if (track) trackWalkKey(code, code, true);
    const event = createKeyboardEvent("keydown", code);
    keydownHandlers.current.forEach((handler) => handler(event));
  }, [trackWalkKey]);

  const handleKeyUp = useCallback((code: number, track = true) => {
    if (track) trackWalkKey(code, code, false);
    const event = createKeyboardEvent("keyup", code);
    keyupHandlers.current.forEach((handler) => handler(event));
  }, [trackWalkKey]);

  const updateArrow = useCallback((code: string, down: boolean) => {
    const held = heldArrows.current;
    trackWalkKey(code, KEY_ALIAS[code], down);
    const previous = arrowKeypadCode(held);
    if (down) held.add(code);
    else held.delete(code);
    const next = arrowKeypadCode(held);
    if (next === previous) return;
    if (previous) handleKeyUp(previous, false);
    if (next) handleKeyDown(next, false);
  }, [handleKeyDown, handleKeyUp, trackWalkKey]);

  const releaseArrows = useCallback(() => {
    const code = arrowKeypadCode(heldArrows.current);
    heldArrows.current.clear();
    walkKeys.current.clear();
    writeWalkKey.current("");
    if (code) handleKeyUp(code);
  }, [handleKeyUp]);

  const handleDocumentKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.code.startsWith("Arrow")) {
        e.preventDefault();
        updateArrow(e.code, true);
        return;
      }
      handleKeyDown(KEY_ALIAS[e.code] ?? e.keyCode);
    },
    [handleKeyDown, updateArrow],
  );

  const handleDocumentKeyUp = useCallback(
    (e: KeyboardEvent) => {
      if (e.code.startsWith("Arrow")) {
        e.preventDefault();
        updateArrow(e.code, false);
        return;
      }
      handleKeyUp(KEY_ALIAS[e.code] ?? e.keyCode);
    },
    [handleKeyUp, updateArrow],
  );

  useEffect(() => {
    if (joystickCode === joystickCodeBefore.current) {
      return;
    }
    if (joystickCodeBefore.current) {
      handleKeyUp(joystickCodeBefore.current);
    }
    if (joystickCode) {
      handleKeyDown(joystickCode);
    }
    joystickCodeBefore.current = joystickCode;
  }, [joystickCode, joystickCodeBefore, handleKeyDown, handleKeyUp]);

  const start = useCallback(async () => {
    const server = await openServerSave();
    let saveFileBody = server.data;
    if (!saveFileBody) {
      saveFileBody = await readLegacySave("mod_jjangjjangman", saveFile);
      if (saveFileBody) await server.write(saveFileBody);
    }
    const joystick = nipple.create({
      zone: mobileController.current!,
    });
    blockAddEventListener(document, ["keydown", "keyup", "keypress"]);
    const { fs, main } = await createDos(canvas.current!);
    await fs.extract("/static/game/mod_jjangjjangman.zip?v=1.7");
    writeWalkKey.current = digit => fs.fs.writeFile("WALK.KEY", Uint8Array.of(digit.charCodeAt(0) || 0));
    writeWalkKey.current("");
    if (saveFileBody) {
      // Overwrite Save File
      (fs as any).fs.writeFile(saveFile, saveFileBody); // eslint-disable-line @typescript-eslint/no-explicit-any
    }
    await main(["-c", "KOEI.COM"]);
    keydownHandlers.current = getBlockedHandler(document, "keydown");
    keyupHandlers.current = getBlockedHandler(document, "keyup");
    restoreAddEventListener(document);

    document.addEventListener("keydown", handleDocumentKeyDown);
    document.addEventListener("keyup", handleDocumentKeyUp);

    joystick.on("move", (_, data) => {
      if (data.force > 0.3) {
        setJoystickCode(
          JOYSTICK_MAPS[(Math.floor((data.angle.degree - 22.5) / 45) + 8) % 8],
        );
      } else {
        setJoystickCode(null);
      }
    });

    joystick.on("end", () => {
      setJoystickCode(null);
    });

    let pending = Promise.resolve();
    detectFileChange(fs, saveFile, () => {
      const bytes = new Uint8Array(fs.fs.readFile(saveFile));
      pending = pending.then(async () => {
        await server.write(bytes);
        setError("");
        setToastMessage("서버에 저장했습니다.");
      }).catch((err: Error) => setError(err.message));
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    handleResize();

    document.addEventListener("fullscreenchange", handleFullScreenChange);

    window.addEventListener("resize", handleResize);
    window.addEventListener("beforeunload", handleBeforeUnload);

    window.addEventListener("blur", releaseArrows);
    start().catch((err: Error) => {
      restoreAddEventListener(document);
      setError(err.message || "게임을 시작할 수 없습니다. 새로고침해 주세요.");
    });

    return () => {
      window.removeEventListener("blur", releaseArrows);
      releaseArrows();
      document.removeEventListener("keydown", handleDocumentKeyDown);
      document.removeEventListener("keyup", handleDocumentKeyUp);
      document.removeEventListener("fullscreenchange", handleFullScreenChange);
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("resize", handleResize);
    };
  }, [
    handleResize,
    handleBeforeUnload,
    handleFullScreenChange,
    handleDocumentKeyDown,
    handleDocumentKeyUp,
    start,
    releaseArrows,
  ]);

  const toggleFullscreen = useCallback(() => {
    const doc = window.document;
    if (!doc.fullscreenElement) {
      doc.documentElement.requestFullscreen();
      if ((navigator as any).keyboard) {
        (navigator as any).keyboard.lock(["Escape"]);
      }
    } else {
      doc.exitFullscreen();
    }
  }, []);

  const toggleKeyboard = useCallback(() => {
    setEnabledToggleKeyboard(!enabledToggleKeyboard);
  }, [enabledToggleKeyboard]);

  const ignoreStopAndPrevent = useCallback((e: Event) => {
    e.stopPropagation();
    e.preventDefault();
  }, []);

  return (
    <div class="game">
      <div class="game__header" onMouseDown={(e) => e.preventDefault()}>
        <div class="game__header__nav">
          <div class="flex flex-row landscape:flex-col">
            <button
              type="button"
              class="game__header__item"
              title="전체화면"
              onClick={toggleFullscreen}
            >
              {enabledToggleFullscreen ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="size-6"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 9V4.5M9 9H4.5M9 9 3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5 5.25 5.25"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="size-6"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15"
                  />
                </svg>
              )}
            </button>
            <button
              type="button"
              class={`game__header__item ${enabledToggleKeyboard ? "" : "game__header__item--disabled"}`}
              title="터치 조이스틱·가상 키패드"
              aria-pressed={enabledToggleKeyboard}
              onClick={toggleKeyboard}
            >
              <svg version="1.1" viewBox="0 0 128 128">
                <path d="M125.5,28.1c-1.667,-1.667 -3.679,-2.501 -6.034,-2.501l-110.933,0c-2.355,0 -4.366,0.834 -6.033,2.501c-1.666,1.667 -2.5,3.678 -2.5,6.033l0,59.733c0,2.356 0.834,4.366 2.5,6.033c1.667,1.667 3.678,2.502 6.033,2.502l110.933,0c2.355,0 4.367,-0.835 6.034,-2.502c1.666,-1.667 2.5,-3.677 2.5,-6.033l0,-59.733c0,-2.355 -0.834,-4.366 -2.5,-6.033Zm-6.034,65.766l-110.933,0l0,-59.733l110.933,0l0,59.733Z" />
                <path d="M18.133,85.332l6.4,0c0.711,0 1.067,-0.356 1.067,-1.067l0,-6.399c0,-0.71 -0.355,-1.067 -1.067,-1.067l-6.4,0c-0.711,0 -1.067,0.357 -1.067,1.067l0,6.399c0,0.711 0.356,1.067 1.067,1.067Z" />
                <path d="M18.133,68.267l14.933,0c0.711,0 1.068,-0.357 1.068,-1.068l0,-6.4c0,-0.711 -0.357,-1.066 -1.068,-1.066l-14.933,0c-0.711,0 -1.067,0.355 -1.067,1.066l0,6.4c0,0.711 0.356,1.068 1.067,1.068Z" />
                <path d="M18.133,51.199l6.4,0c0.711,0 1.067,-0.356 1.067,-1.067l0,-6.399c0,-0.711 -0.355,-1.066 -1.067,-1.067l-6.4,0c-0.711,0 -1.067,0.356 -1.067,1.067l0,6.399c0,0.711 0.356,1.067 1.067,1.067Z" />
                <path d="M92.801,76.799l-57.6,0c-0.712,0 -1.067,0.357 -1.067,1.068l0,6.399c0,0.709 0.355,1.067 1.067,1.067l57.597,0c0.712,0 1.068,-0.356 1.068,-1.067l0,-6.399c0,-0.711 -0.356,-1.068 -1.065,-1.068Z" />
                <path d="M42.667,67.199c0,0.711 0.355,1.068 1.066,1.068l6.4,0c0.711,0 1.066,-0.357 1.066,-1.068l0,-6.4c0,-0.711 -0.354,-1.066 -1.066,-1.066l-6.4,0c-0.711,0 -1.066,0.355 -1.066,1.066l0,6.4Z" />
                <path d="M35.201,51.199l6.399,0c0.711,0 1.067,-0.356 1.067,-1.067l0,-6.399c0,-0.711 -0.356,-1.066 -1.067,-1.067l-6.399,0c-0.712,0 -1.067,0.356 -1.067,1.067l0,6.399c0,0.711 0.356,1.067 1.067,1.067Z" />
                <path d="M59.733,67.199c0,0.711 0.356,1.068 1.066,1.068l6.4,0c0.711,0 1.068,-0.357 1.068,-1.068l0,-6.4c0,-0.711 -0.357,-1.066 -1.068,-1.066l-6.4,0c-0.71,0 -1.066,0.355 -1.066,1.066l0,6.4Z" />
                <path d="M52.266,51.199l6.4,0c0.711,0 1.067,-0.356 1.067,-1.067l0,-6.399c0,-0.711 -0.355,-1.066 -1.067,-1.067l-6.4,0c-0.711,0 -1.067,0.356 -1.067,1.067l0,6.399c0,0.711 0.356,1.067 1.067,1.067Z" />
                <path d="M76.8,67.199c0,0.711 0.356,1.068 1.065,1.068l6.401,0c0.711,0 1.066,-0.357 1.066,-1.068l0,-6.4c0,-0.711 -0.355,-1.066 -1.066,-1.066l-6.401,0c-0.709,0 -1.065,0.355 -1.065,1.066l0,6.4Z" />
                <path d="M109.866,76.799l-6.399,0c-0.712,0 -1.068,0.357 -1.068,1.068l0,6.399c0,0.709 0.356,1.067 1.068,1.067l6.399,0c0.711,0 1.067,-0.356 1.067,-1.067l0,-6.399c0,-0.711 -0.355,-1.068 -1.067,-1.068Z" />
                <path d="M69.333,51.199l6.401,0c0.711,0 1.066,-0.356 1.066,-1.067l0,-6.399c0,-0.711 -0.355,-1.066 -1.066,-1.067l-6.401,0c-0.711,0 -1.066,0.356 -1.066,1.067l0,6.399c0,0.711 0.355,1.067 1.066,1.067Z" />
                <path d="M86.4,51.199l6.399,0c0.711,0 1.067,-0.356 1.067,-1.067l0,-6.399c0,-0.711 -0.356,-1.066 -1.067,-1.067l-6.399,0c-0.711,0 -1.068,0.356 -1.068,1.067l0,6.399c0,0.711 0.357,1.067 1.068,1.067Z" />
                <path d="M93.866,67.199c0,0.711 0.355,1.068 1.066,1.068l14.933,0c0.712,0 1.068,-0.357 1.068,-1.068l0,-23.466c0,-0.711 -0.355,-1.066 -1.068,-1.067l-6.399,0c-0.711,0 -1.067,0.356 -1.067,1.067l0,16l-7.467,0c-0.711,0 -1.066,0.355 -1.066,1.066l0,6.4l0,0Z" />
              </svg>
            </button>
          </div>
        </div>

      </div>

      <div
        class="game__screen"
        onPointerDownCapture={blockGameMouse}
        onPointerMoveCapture={blockGameMouse}
        onPointerUpCapture={blockGameMouse}
        onMouseDownCapture={blockGameMouse}
        onMouseMoveCapture={blockGameMouse}
        onMouseUpCapture={blockGameMouse}
        onClickCapture={blockGameMouse}
        onContextMenuCapture={blockGameMouse}
        onWheelCapture={blockGameMouse}
        style={{
          "--screen-width": `${width}px`,
          "--screen-height": `${height}px`,
        }}
        ref={screen}
      >
        <div class="game__canvas">
          <canvas ref={canvas} />
        </div>

        <div
          class="game__event-blocker"
          hidden={!enabledToggleKeyboard}
          ref={mobileController}
          onTouchStart={ignoreStopAndPrevent}
          onTouchEnd={ignoreStopAndPrevent}
          onTouchMove={ignoreStopAndPrevent}
        />
        {enabledToggleKeyboard && (
          <VirtualKeyboard onKeyDown={handleKeyDown} onKeyUp={handleKeyUp} />
        )}
      </div>

      <div class={`toast ${(error || toastMessage) ? "toast--active" : ""}`}>
        {error || innerToastMessage}
      </div>
    </div>
  );
}
