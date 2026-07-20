(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const body = document.body;
  const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";

  function post(url, data) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(data),
    }).then((r) => r.json());
  }

  function toast(msg) {
    const t = $("[data-toast]");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(window.__tt);
    window.__tt = setTimeout(() => t.classList.remove("show"), 2600);
  }

  const money = (n) => "$" + Number(n).toFixed(2);

  /* ---------- Age gate ---------- */
  const gate = $("[data-age-gate]");
  if (gate) {
    body.style.overflow = "hidden";
    const chk = $("[data-age-check]"), enter = $("[data-age-enter]");
    chk && chk.addEventListener("change", () => (enter.disabled = !chk.checked));
    enter && enter.addEventListener("click", () => {
      gate.classList.add("hidden");
      body.style.overflow = "";
    });
  }

  /* ---------- Cookie ---------- */
  $$("[data-cookie-dismiss]").forEach((b) =>
    b.addEventListener("click", () => $("[data-cookie]").classList.add("hidden"))
  );

  /* ---------- Cart ---------- */
  const drawer = $("[data-cart-drawer]"), overlay = $("[data-cart-overlay]");
  function openCart() { drawer.classList.add("open"); overlay.classList.add("open"); }
  function closeCart() { drawer.classList.remove("open"); overlay.classList.remove("open"); }
  $$("[data-cart-open]").forEach((b) => b.addEventListener("click", openCart));
  $("[data-cart-close]") && $("[data-cart-close]").addEventListener("click", closeCart);
  overlay && overlay.addEventListener("click", closeCart);

  function renderCart(state) {
    $$("[data-cart-count]").forEach((e) => (e.textContent = state.count));
    $("[data-cart-total]") && ($("[data-cart-total]").textContent = money(state.total));
    const bodyEl = $("[data-cart-body]");
    if (!bodyEl) return;
    if (!state.items.length) {
      bodyEl.innerHTML = '<p class="cart-empty">Your cart is empty.</p>';
      return;
    }
    bodyEl.innerHTML = state.items.map((i) => `
      <div class="cart-item">
        <div class="ci-info">
          <div class="ci-name">${i.name}</div>
          <div class="ci-meta">${money(i.unit_price || i.price)} / vial${
            +i.bulk_pct ? ` <span class="ci-save">−${i.bulk_pct}% bulk</span>` : ""}</div>
          <div class="ci-qty">
            <button data-dec="${i.id}">−</button><span>${i.qty}</span><button data-inc="${i.id}">+</button>
            <span class="ci-line">${money(i.line_total)}</span>
          </div>
        </div>
      </div>`).join("");
    const sv = $("[data-cart-savings]");
    if (sv) {
      const s = parseFloat(state.savings || 0);
      sv.textContent = s > 0 ? `You're saving ${money(state.savings)} with bulk pricing` : "";
    }
    $$("[data-inc]", bodyEl).forEach((b) => b.addEventListener("click", () =>
      change(b.dataset.inc, +1)));
    $$("[data-dec]", bodyEl).forEach((b) => b.addEventListener("click", () =>
      change(b.dataset.dec, -1)));
  }

  const qtyOf = (id, state) => (state.items.find((i) => String(i.id) === String(id)) || {}).qty || 0;
  let lastState = { count: 0, total: 0, items: [] };
  function change(id, delta) {
    post(body.dataset.cartUpdateUrl, { product_id: id, qty: qtyOf(id, lastState) + delta })
      .then((s) => { lastState = s; renderCart(s); });
  }

  function qtyFromControls(btn) {
    // Product page: an optional [data-qty-input] near the button sets quantity.
    const scope = btn.closest("[data-buybox]") || document;
    const input = scope.querySelector("[data-qty-input]");
    const n = input ? parseInt(input.value, 10) : 1;
    return Number.isFinite(n) && n > 0 ? n : 1;
  }

  $$("[data-add]").forEach((btn) =>
    btn.addEventListener("click", () => {
      post(body.dataset.cartAddUrl, { product_id: btn.dataset.add, qty: qtyFromControls(btn) }).then((s) => {
        lastState = s; renderCart(s); openCart(); toast(btn.dataset.name + " added to cart");
      });
    })
  );

  /* Quantity steppers on the product buy-box */
  $$("[data-qty-step]").forEach((b) => b.addEventListener("click", () => {
    const scope = b.closest("[data-buybox]") || document;
    const input = scope.querySelector("[data-qty-input]");
    if (!input) return;
    const n = Math.max(1, (parseInt(input.value, 10) || 1) + parseInt(b.dataset.qtyStep, 10));
    input.value = n;
    const tier = scope.querySelector("[data-tier-hint]");
    if (tier) {
      const pct = n >= 10 ? 15 : n >= 5 ? 10 : n >= 3 ? 5 : 0;
      tier.textContent = pct ? `${pct}% bulk discount applied` : "Buy 3+ to unlock bulk pricing";
    }
  }));

  /* ---------- Checkout ---------- */
  const coForm = $("[data-checkout-form]");
  coForm && coForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(coForm));
    post(body.dataset.checkoutUrl, fd).then((r) => {
      if (!r.ok) { toast(r.error || "Cart is empty"); return; }
      lastState = { count: 0, total: 0, items: [] };
      renderCart(lastState);
      toast(r.message || "Order received");
    });
  });

  /* ---------- Contact ---------- */
  $$("[data-contact-form]").forEach((f) =>
    f.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(f));
      fd.kind = "contact";
      post(body.dataset.contactUrl, fd).then((r) => { f.reset(); toast(r.message || "Thanks!"); });
    })
  );

  /* ---------- Category filter ---------- */
  const filterWrap = $("[data-cat-filter]");
  if (filterWrap) {
    $$(".cat-chip", filterWrap).forEach((chip) =>
      chip.addEventListener("click", () => {
        $$(".cat-chip", filterWrap).forEach((c) => c.classList.remove("is-active"));
        chip.classList.add("is-active");
        const f = chip.dataset.filter;
        $$("[data-grid] .pcard").forEach((card) => {
          card.style.display = f === "all" || card.dataset.cat === f ? "" : "none";
        });
      })
    );
  }

  // Prime cart state on load.
  fetch("/cart/").then((r) => r.json()).then((s) => { lastState = s; renderCart(s); });
})();
