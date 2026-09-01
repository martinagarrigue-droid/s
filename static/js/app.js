(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function setText(el, text) {
    if (el) el.textContent = text == null ? "" : text;
  }

  function setHidden(el, hidden) {
    if (el) el.hidden = hidden;
  }

  function setDisabled(el, disabled) {
    if (el) el.disabled = disabled;
  }

  var openBtns = document.querySelectorAll(".js-open-calculator");
  var overlay = $("calc-overlay");
  var closeBtn = $("calc-close");
  var form = $("calc-form");
  var submitBtn = $("calc-submit");
  var statusEl = $("calc-status");
  var errorEl = $("calc-error");
  var resultEl = $("calc-result");
  var readoutEl = $("calc-readout");
  var paragraphOneEl = $("calc-paragraph-one");
  var paragraphTwoEl = $("calc-paragraph-two");
  var hookEl = $("calc-hook");
  var buyBtn = $("calc-buy");
  var priceEl = $("calc-price");
  var buyStatusEl = $("calc-buy-status");

  var lastPayload = null;

  function formatPriceArs(amount) {
    if (typeof amount !== "number") return "A confirmar";
    try {
      return amount.toLocaleString("es-AR") + " ARS";
    } catch (err) {
      return amount + " ARS";
    }
  }

  function openModal() {
    setHidden(overlay, false);
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    setHidden(overlay, true);
    document.body.style.overflow = "";
  }

  function resetBuyState() {
    setDisabled(buyBtn, false);
    setHidden(buyBtn, false);
    setText(buyBtn, "Comprar informe completo");
    setHidden(buyStatusEl, true);
    setText(buyStatusEl, "");
  }

  function resetView() {
    lastPayload = null;
    setHidden(form, false);
    setHidden(resultEl, true);
    setHidden(errorEl, true);
    setText(errorEl, "");
    setHidden(statusEl, true);
    setText(statusEl, "");
    setDisabled(submitBtn, false);
    setText(submitBtn, "Calcular mi carta");
    resetBuyState();
  }

  function showError(message) {
    setHidden(statusEl, true);
    setHidden(errorEl, false);
    setText(errorEl, message || "No pudimos conectar con el servidor. Probá de nuevo.");
    setDisabled(submitBtn, false);
    setText(submitBtn, "Calcular mi carta");
  }

  openBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      resetView();
      openModal();
    });
  });

  if (closeBtn) closeBtn.addEventListener("click", closeModal);

  if (overlay) {
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) closeModal();
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && overlay && !overlay.hidden) closeModal();
  });

  function parseJsonSafely(response) {
    return response
      .json()
      .then(function (data) {
        return { ok: response.ok, data: data };
      })
      .catch(function () {
        return { ok: response.ok, data: null };
      });
  }

  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();

      setHidden(errorEl, true);
      setHidden(statusEl, false);
      setText(statusEl, "Calculando coordenadas...");
      setDisabled(submitBtn, true);
      setText(submitBtn, "Calculando…");

      var dateField = form.elements.namedItem("date");
      var timeField = form.elements.namedItem("time");
      var locationField = form.elements.namedItem("location");

      var payload = {
        date: dateField ? dateField.value : "",
        time: timeField ? timeField.value : "",
        location: locationField ? locationField.value.trim() : "",
      };

      fetch("/api/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(parseJsonSafely)
        .then(function (result) {
          if (!result.ok) {
            var message =
              result.data && typeof result.data.detail === "string"
                ? result.data.detail
                : "No pudimos calcular tu carta. Probá de nuevo.";
            throw new Error(message);
          }

          var data = result.data || {};
          var teaser = data.teaser || {};

          lastPayload = payload;

          setHidden(form, true);
          setHidden(statusEl, true);
          setHidden(resultEl, false);
          resetBuyState();

          setText(
            readoutEl,
            "Sol · " + (teaser.sun_sign || "—") + " — Ascendente · " + (teaser.ascendant_sign || "—")
          );
          setText(paragraphOneEl, teaser.paragraph_one);
          setText(paragraphTwoEl, teaser.paragraph_two);
          setText(hookEl, teaser.hook);
          setText(priceEl, formatPriceArs(data.full_report_price_ars));
        })
        .catch(function (err) {
          showError(err && err.message);
        });
    });
  }

  if (buyBtn) {
    buyBtn.addEventListener("click", function () {
      if (!lastPayload) return;

      setDisabled(buyBtn, true);
      setText(buyBtn, "Conectando pasarela...");
      setHidden(buyStatusEl, true);

      fetch("/api/create-preference", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(lastPayload),
      })
        .then(parseJsonSafely)
        .then(function (result) {
          var data = result.data || {};

          if (result.ok && data.init_point) {
            window.location.href = data.init_point;
            return;
          }

          var message =
            (data && typeof data.message === "string" && data.message) ||
            (data && typeof data.detail === "string" && data.detail) ||
            "No pudimos iniciar el pago. Probá de nuevo en un rato.";

          setHidden(buyStatusEl, false);
          setText(buyStatusEl, message);
          setDisabled(buyBtn, false);
          setText(buyBtn, "Comprar informe completo");
        })
        .catch(function () {
          setHidden(buyStatusEl, false);
          setText(buyStatusEl, "No pudimos conectar con el servidor. Probá de nuevo.");
          setDisabled(buyBtn, false);
          setText(buyBtn, "Comprar informe completo");
        });
    });
  }
})();
