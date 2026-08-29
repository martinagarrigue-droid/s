(function () {
  "use strict";

  var openBtn = document.getElementById("calc-open");
  var overlay = document.getElementById("calc-overlay");
  var closeBtn = document.getElementById("calc-close");
  var form = document.getElementById("calc-form");
  var submitBtn = document.getElementById("calc-submit");
  var statusEl = document.getElementById("calc-status");
  var errorEl = document.getElementById("calc-error");
  var resultEl = document.getElementById("calc-result");
  var resultSubjectEl = document.getElementById("calc-result-subject");
  var resultTextEl = document.getElementById("calc-result-text");
  var downloadLink = document.getElementById("calc-download");

  function openModal() {
    overlay.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    overlay.hidden = true;
    document.body.style.overflow = "";
  }

  function resetView() {
    form.hidden = false;
    resultEl.hidden = true;
    errorEl.hidden = true;
    errorEl.textContent = "";
    statusEl.hidden = true;
    statusEl.textContent = "";
    submitBtn.disabled = false;
    submitBtn.textContent = "Calcular mi carta";
  }

  openBtn.addEventListener("click", function () {
    resetView();
    openModal();
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
        form.hidden = true;
        statusEl.hidden = true;
        resultEl.hidden = false;
        resultSubjectEl.textContent =
          (data.subject && data.subject.place && data.subject.place.resolved_display_name) ||
          payload.location;
        resultTextEl.textContent = data.report_text || "";

        if (data.pdf_url) {
          downloadLink.href = data.pdf_url;
          downloadLink.hidden = false;
        } else {
          downloadLink.hidden = true;
        }
      })
      .catch(function (err) {
        statusEl.hidden = true;
        errorEl.hidden = false;
        errorEl.textContent = err.message || "No pudimos conectar con el servidor. Probá de nuevo.";
        submitBtn.disabled = false;
        submitBtn.textContent = "Calcular mi carta";
      });
  });
})();
