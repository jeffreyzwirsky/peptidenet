(function () {
  const root = document.querySelector("[data-ai-widget]");
  if (!root) return;
  const panel = root.querySelector("[data-ai-panel]");
  const log = root.querySelector("[data-ai-log]");
  const form = root.querySelector("[data-ai-form]");
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";

  root.querySelectorAll("[data-ai-toggle]").forEach((b) =>
    b.addEventListener("click", () => { panel.hidden = !panel.hidden; if (!panel.hidden) form.question.focus(); })
  );

  function add(text, who) {
    const d = document.createElement("div");
    d.className = "ai-msg " + who;
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = form.question.value.trim();
    if (!q) return;
    add(q, "me");
    form.question.value = "";
    const thinking = add("…", "bot thinking");
    fetch("/ai/ask/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" },
      body: JSON.stringify({ question: q, company_website: form.company_website.value }),
    })
      .then((r) => r.json())
      .then((d) => { thinking.remove(); add(d.answer || d.error || "Sorry, try again.", "bot"); })
      .catch(() => { thinking.remove(); add("Sorry, the assistant is unavailable right now.", "bot"); });
  });
})();
