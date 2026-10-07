// The entrance plays once (owner 2026-10-07: «при нажатии ⌘. интерфейс заново анимируется как при старте»).
// The crumb's grow, the round buttons' pop and the controls' landing are CSS animations on classes (ui/look.css
// .hy-open #crumb, .hy-pop, .hy-grow; canvas.html .intro). Hiding the interface (⌘.) gives the same elements its own
// animation; when it ends, their entrance animation is theirs again and the browser plays it from the start. So hiding
// the interface ends the entrance for good: the classes go, and showing it reverses the hide only.
//   hyEntranceDone()   the board (canvas.html uiHide) and the library page around it (v2.html setUiHidden) call it
(() => {
  window.hyEntranceDone = () => {
    document.documentElement.classList.remove("hy-open", "intro");
    document.querySelectorAll(".hy-pop, .hy-grow").forEach(e => e.classList.remove("hy-pop", "hy-grow"));
  };
})();
