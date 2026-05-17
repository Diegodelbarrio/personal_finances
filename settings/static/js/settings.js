document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initScoreBars();
    initDirtyState();
    initRecommendationButtons();
});

function initToasts() {
    if (!window.bootstrap) {
        return;
    }

    var toastElements = [].slice.call(document.querySelectorAll(".toast"));
    toastElements.forEach(function (toastEl) {
        var toast = new bootstrap.Toast(toastEl, { delay: 3200 });
        toast.show();
    });
}

function initRecommendationButtons() {
    var buttons = document.querySelectorAll(".js-apply-recommendation");
    buttons.forEach(function (button) {
        button.addEventListener("click", function () {
            var targetField = button.getAttribute("data-target-field");
            var value = button.getAttribute("data-value");
            if (!targetField) {
                return;
            }

            var input = document.querySelector('[name="' + targetField + '"]');
            if (!input) {
                return;
            }

            input.value = value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
            input.focus();

            button.classList.remove("btn-outline-primary");
            button.classList.add("btn-success");
            button.innerHTML = '<i class="bi bi-check2 me-1"></i>Applied';
        });
    });
}

function initScoreBars() {
    var bars = document.querySelectorAll(".js-score-bar");
    bars.forEach(function (bar) {
        var raw = (bar.getAttribute("data-score") || "").trim();
        var normalized = raw.replace(",", ".");
        var value = parseFloat(normalized);
        if (!isFinite(value)) {
            value = 0;
        }
        value = Math.max(0, Math.min(100, value));
        bar.style.width = value + "%";
        bar.setAttribute("aria-valuenow", String(Math.round(value)));
    });
}

function initDirtyState() {
    var form = document.getElementById("settings-form");
    if (!form) {
        return;
    }

    var submitButton = document.getElementById("settings-submit");
    var resetButton = document.getElementById("settings-reset");
    var saveState = document.getElementById("settings-save-state");
    var initialState = serializeForm(form);

    function setDirtyState() {
        var isDirty = serializeForm(form) !== initialState;

        if (submitButton) {
            submitButton.disabled = !isDirty;
        }
        if (resetButton) {
            resetButton.hidden = !isDirty;
        }
        if (saveState) {
            saveState.classList.toggle("is-dirty", isDirty);
            saveState.innerHTML = isDirty
                ? '<i class="bi bi-exclamation-circle"></i>Unsaved changes'
                : '<i class="bi bi-check2-circle"></i>All changes saved';
        }
    }

    form.addEventListener("input", setDirtyState);
    form.addEventListener("change", setDirtyState);

    if (resetButton) {
        resetButton.addEventListener("click", function () {
            form.reset();
            resetRecommendationButtons();
            setDirtyState();
        });
    }

    setDirtyState();
}

function resetRecommendationButtons() {
    var buttons = document.querySelectorAll(".js-apply-recommendation");
    buttons.forEach(function (button) {
        button.classList.remove("btn-success");
        button.classList.add("btn-outline-primary");
        button.innerHTML = '<i class="bi bi-arrow-down-left-circle me-1"></i>Apply';
    });
}

function serializeForm(form) {
    var data = new FormData(form);
    var entries = [];

    data.forEach(function (value, key) {
        if (key !== "csrfmiddlewaretoken") {
            entries.push(key + "=" + value);
        }
    });

    return entries.sort().join("&");
}
