// Render stored UTC timestamps in the browser's local timezone,
// and remember the last-used webhook URL in localStorage.
(() => {
  const fmt = new Intl.DateTimeFormat(undefined, {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
  document.querySelectorAll("time[data-utc]").forEach((el) => {
    const raw = el.getAttribute("data-utc");
    const d = new Date(raw);
    if (!isNaN(d.valueOf())) el.textContent = fmt.format(d);
  });

  const KEY = "discord_scheduler.last_webhook";
  const input = document.getElementById("webhook_url");
  if (!input) return;
  if (!input.value) {
    const saved = localStorage.getItem(KEY);
    if (saved) input.value = saved;
  }
  input.form?.addEventListener("submit", () => {
    if (input.value) localStorage.setItem(KEY, input.value);
  });
})();
