(function () {
  "use strict";

  var openBtns = document.querySelectorAll(".js-open-calculator");
  var overlay = document.getElementById("calc-overlay");
  var closeBtn = document.getElementById("calc-close");
  var form = document.getElementById("calc-form");
  var submitBtn = document.getElementById("calc-submit");
  var statusEl = document.getElementById("calc-status");
  var errorEl = document.getElementById("calc-error");
  var resultEl = document.getElementById("calc-result");
  var resultSubjectEl = document.getElementById("calc-result-subject");
  var teaserPhraseEl = document.getElementById("calc-teaser-phrase");
  var buyBtn = document.getElementById("calc-buy");
  var priceEl = document.getElementById("calc-price");
  var buyStatusEl = document.getElementById("calc-buy-status");

  var lastPayload = null;

  function formatPriceArs(amount) {
    if (typeof amount !== "number") return "";
    try {
      return amount.toLocaleString("es-AR") + " ARS";
    } catch (err) {
      return amount + " ARS";
    }
  }

  function openModal() {
    overlay.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    overlay.hidden = true;
    document.body.style.overflow = "";
  }

  function resetBuyState() {
    buyBtn.disabled = false;
    buyBtn.hidden = false;
    buyBtn.textContent = "Comprar informe completo";
    buyStatusEl.hidden = true;
    buyStatusEl.textContent = "";
  }

  function resetView() {
    lastPayload = null;
    form.hidden = false;
    resultEl.hidden = true;
    errorEl.hidden = true;
    errorEl.textContent = "";
    statusEl.hidden = true;
    statusEl.textContent = "";
    submitBtn.disabled = false;
    submitBtn.textContent = "Calcular mi carta";
    resetBuyState();
  }

  openBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      resetView();
      openModal();
    });
  });

  closeBtn.addEventListener("click", closeModal);

  overlay.addEventListener("click", function (event) {
    if (event.target === overlay) closeModal();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !overlay.hidden) closeModal();
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    errorEl.hidden = true;
    statusEl.hidden = false;
    statusEl.textContent = "Calculando coordenadas...";
    submitBtn.disabled = true;
    submitBtn.textContent = "Calculando…";

    var payload = {
      date: form.date.value,
      time: form.time.value,
      location: form.location.value.trim(),
    };

    fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        }).catch(function () {
          return { ok: response.ok, data: null };
        });
      })
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

        form.hidden = true;
        statusEl.hidden = true;
        resultEl.hidden = false;
        resetBuyState();

        resultSubjectEl.textContent =
          "Sol en " + (teaser.sun_sign || "—") + " · Ascendente en " + (teaser.ascendant_sign || "—");
        teaserPhraseEl.textContent = teaser.phrase || "";
        priceEl.textContent = formatPriceArs(data.full_report_price_ars);
      })
      .catch(function (err) {
        statusEl.hidden = true;
        errorEl.hidden = false;
        errorEl.textContent = err.message || "No pudimos conectar con el servidor. Probá de nuevo.";
        submitBtn.disabled = false;
        submitBtn.textContent = "Calcular mi carta";
      });
  });

  buyBtn.addEventListener("click", function () {
    if (!lastPayload) return;

    buyBtn.disabled = true;
    buyBtn.textContent = "Procesando…";
    buyStatusEl.hidden = true;

    fetch("/api/create-preference", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lastPayload),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        }).catch(function () {
          return { ok: response.ok, data: null };
        });
      })
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

        buyStatusEl.hidden = false;
        buyStatusEl.textContent = message;
        buyBtn.disabled = false;
        buyBtn.textContent = "Comprar informe completo";
      })
      .catch(function () {
        buyStatusEl.hidden = false;
        buyStatusEl.textContent = "No pudimos conectar con el servidor. Probá de nuevo.";
        buyBtn.disabled = false;
        buyBtn.textContent = "Comprar informe completo";
      });
  });
})();
