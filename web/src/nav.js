// Shared mobile hamburger menu behaviour (ported from base.html).
export function initNav() {
  const btn = document.getElementById("hamburger-btn");
  const menu = document.getElementById("mobile-menu");
  if (!btn || !menu) return;

  btn.addEventListener("click", () => {
    menu.classList.toggle("open");
    btn.textContent = menu.classList.contains("open") ? "✕" : "☰";
  });
  menu.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => {
      menu.classList.remove("open");
      btn.textContent = "☰";
    }),
  );
}
