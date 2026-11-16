import logo from "../assets/logo.gif";

export function Splash({ onStart }: { onStart: () => void }) {
  return (
    <div class="splash">
      <img src={logo} class="px-4" alt="대항해시대2" />
      <div class="menu">
        <div class="corner corner-tl" />
        <div class="corner corner-tr" />
        <div class="corner corner-bl" />
        <div class="corner corner-br" />
        <button type="button" class="menu__item" onClick={onStart}>
          대항해시대2 짱짱맨 실행 <span class="italic">v1.6</span>
        </button>
      </div>
    </div>
  );
}
