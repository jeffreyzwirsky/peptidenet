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
      // Remember the confirmation for a year so the gate doesn't reappear on
      // every page. The server also skips rendering the gate when this cookie
      // is present (see base.html), so there's no flash on later visits.
      try {
        var secure = location.protocol === "https:" ? "; Secure" : "";
        document.cookie = "age_ok=1; path=/; max-age=31536000; SameSite=Lax" + secure;
      } catch (e) {}
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
    // `qty` is packs; `vials` is what ships. Both are shown, because the number
    // beside the +/− buttons is the one people sanity-check against their
    // receipt, and "2" meaning twenty vials is not self-evident.
    bodyEl.innerHTML = state.items.map((i) => `
      <div class="cart-item">
        <div class="ci-info">
          <div class="ci-name">${i.name}</div>
          <div class="ci-meta">${money(i.unit_price || i.pack_price || i.price)} / ${
            i.pack_label || "unit"}${
            +i.bulk_pct ? ` <span class="ci-save">−${i.bulk_pct}% bulk</span>` : ""}</div>
          <div class="ci-qty">
            <button data-dec="${i.id}" aria-label="Remove one pack">−</button>
            <span>${i.qty}</span>
            <button data-inc="${i.id}" aria-label="Add one pack">+</button>
            ${i.sells_in_packs ? `<span class="ci-vials">${i.vials} vials</span>` : ""}
            <span class="ci-line">${money(i.line_total)}</span>
          </div>
        </div>
      </div>`).join("");
    const sv = $("[data-cart-savings]");
    if (sv) {
      const s = parseFloat(state.savings || 0);
      sv.textContent = s > 0 ? `You're saving ${money(state.savings)} with bulk pricing` : "";
    }
    const vc = $("[data-cart-vials]");
    if (vc) {
      const v = parseInt(state.vials, 10) || 0;
      vc.textContent = v ? `${v} vial${v === 1 ? "" : "s"} total` : "";
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

  /* Quantity steppers on the product buy-box. The input counts PACKS; the
     live vial readout beside it is what makes that legible. */
  function syncBuybox(scope) {
    const input = scope.querySelector("[data-qty-input]");
    if (!input) return;
    const packs = Math.max(1, parseInt(input.value, 10) || 1);
    input.value = packs;
    const per = parseInt(input.dataset.pack, 10) || 1;
    const vials = scope.querySelector("[data-vial-count]");
    if (vials) vials.textContent = `${packs * per} vial${packs * per === 1 ? "" : "s"}`;
    const tier = scope.querySelector("[data-tier-hint]");
    if (tier) {
      const pct = packs >= 10 ? 15 : packs >= 5 ? 10 : packs >= 3 ? 5 : 0;
      tier.textContent = pct
        ? `${pct}% bulk discount applied`
        : (per > 1 ? "Buy 3+ packs to unlock bulk pricing" : "Buy 3+ to unlock bulk pricing");
    }
  }

  $$("[data-qty-step]").forEach((b) => b.addEventListener("click", () => {
    const scope = b.closest("[data-buybox]") || document;
    const input = scope.querySelector("[data-qty-input]");
    if (!input) return;
    input.value = Math.max(1, (parseInt(input.value, 10) || 1) + parseInt(b.dataset.qtyStep, 10));
    syncBuybox(scope);
  }));

  // Typing straight into the box has to resync too, and can't be allowed to
  // sit at 0 or a fraction of a pack.
  $$("[data-qty-input]").forEach((input) => {
    const scope = input.closest("[data-buybox]") || document;
    input.addEventListener("change", () => syncBuybox(scope));
    syncBuybox(scope);
  });

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
      // Send the buyer to their order page. On a 10-15 day delivery a toast that
      // vanishes after 2.6s is not an acceptable post-purchase experience.
      if (r.status_url) setTimeout(() => { window.location.href = r.status_url; }, 900);
    });
  });

  /* ---------- Product gallery ---------- */
  const pdpPhoto = $("[data-pdp-photo]");
  if (pdpPhoto) {
    $$("[data-pdp-thumb]").forEach((thumb) =>
      thumb.addEventListener("click", () => {
        $$("[data-pdp-thumb]").forEach((t) => t.classList.remove("is-active"));
        thumb.classList.add("is-active");
        pdpPhoto.src = thumb.dataset.src;
        pdpPhoto.alt = thumb.dataset.alt || pdpPhoto.alt;
      })
    );
  }

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

  // Prime cart state — but only when there's something in it. The server already
  // renders the badge count, so firing this on every page load (including for
  // bots) bought an extra round-trip on first paint for nothing.
  if (Number(($("[data-cart-count]") || {}).textContent || 0) > 0) {
    fetch("/cart/").then((r) => r.json()).then((s) => { lastState = s; renderCart(s); });
  }

  /* ---------- Size selector ----------
     Progressive enhancement over real links. Without JS each strength is a
     normal page with its own price and its own URL, which is what a crawler
     and a no-JS visitor need. With JS the price, stock, per-vial figure and
     the add-to-cart target swap in place and the URL is pushed, so picking a
     size feels like one product rather than a page load.

     The add button's data-add is repointed at the selected SKU. Getting that
     wrong would put the wrong strength in the cart at the right price, which
     is the kind of error a customer only finds after paying. */
  const picker = $("[data-size-picker]");
  if (picker) {
    const scope = picker.closest("[data-buybox]") || document;
    const priceEl = $("[data-pdp-price]", scope);
    const wasEl   = $("[data-pdp-was]", scope);
    const unitEl  = $("[data-pdp-unit]", scope);
    const stockEl = $("[data-pdp-stock]", scope);
    const addBtn  = $(".pdp-add", scope);
    const qtyIn   = $("[data-qty-input]", scope);

    function selectSize(opt, push) {
      $$(".size-opt", picker).forEach((a) => {
        a.classList.toggle("on", a === opt);
        if (a === opt) a.setAttribute("aria-current", "true");
        else a.removeAttribute("aria-current");
      });
      const d = opt.dataset;
      if (priceEl) priceEl.textContent = money(d.sizePrice);
      if (unitEl)  unitEl.textContent  = money(d.sizeUnit);
      if (wasEl) {
        // Only show a comparison price when this strength genuinely has one.
        // Carrying the previous size's "was" across would be a fabricated
        // reference price on the new one.
        if (d.sizeWas) { wasEl.textContent = money(d.sizeWas); wasEl.hidden = false; }
        else { wasEl.hidden = true; }
      }
      if (stockEl) {
        stockEl.className = "pdp-stock " + d.sizeStock;
        stockEl.innerHTML = '<span class="dot"></span>' + d.sizeStockLabel;
      }
      if (addBtn) {
        addBtn.dataset.add = d.sizeId;
        addBtn.dataset.pack = d.sizePack;
        addBtn.disabled = d.sizeStock === "out";
        addBtn.textContent = d.sizeStock === "out" ? "Currently sold out" : "Add to cart";
      }
      if (qtyIn) { qtyIn.dataset.pack = d.sizePack; syncBuybox(scope); }
      if (push && window.history && history.pushState) {
        history.pushState({ size: d.sizeSlug }, "", "/product/" + d.sizeSlug + "/");
      }
    }

    $$(".size-opt", picker).forEach((a) =>
      a.addEventListener("click", (e) => {
        e.preventDefault();
        selectSize(a, true);
      })
    );
    // Back/forward has to move the selection too, or the URL and the price
    // disagree — and the price is what the customer trusts.
    window.addEventListener("popstate", () => {
      const slug = location.pathname.replace(/^\/product\/|\/$/g, "");
      const match = $$(".size-opt", picker).find((a) => a.dataset.sizeSlug === slug);
      if (match) selectSize(match, false);
    });
  }
})();
