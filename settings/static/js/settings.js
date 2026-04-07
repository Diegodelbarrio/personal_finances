document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initScoreBars();
    initRecommendationButtons();
});

function initToasts() {
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
            button.textContent = "Applied";
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
