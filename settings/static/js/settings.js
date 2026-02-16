document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initScoreBars();
    initRecommendationButtons();
    initGoalSimulator();
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

function initGoalSimulator() {
    var simulator = document.querySelector(".goal-simulator");
    var monthlyInput = document.getElementById("simulator-monthly-contribution");
    var monthsNode = document.getElementById("simulator-months");
    var dateNode = document.getElementById("simulator-date");
    var statusNode = document.getElementById("simulator-status");

    if (!simulator || !monthlyInput || !monthsNode || !dateNode || !statusNode) {
        return;
    }

    var gap = parseFloat(simulator.getAttribute("data-gap") || "0");
    var targetDateRaw = simulator.getAttribute("data-target-date") || "";
    var targetDate = targetDateRaw ? new Date(targetDateRaw + "T00:00:00") : null;
    var formatDate = new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });

    function refresh() {
        var monthlyContribution = parseFloat(monthlyInput.value || "0");
        if (!isFinite(monthlyContribution) || monthlyContribution < 0) {
            monthlyContribution = 0;
        }

        if (gap <= 0) {
            monthsNode.textContent = "0";
            dateNode.textContent = formatDate.format(new Date());
            statusNode.textContent = "Target reached";
            statusNode.className = "text-success";
            return;
        }

        if (monthlyContribution <= 0) {
            monthsNode.textContent = "--";
            dateNode.textContent = "--";
            statusNode.textContent = "Set a monthly contribution";
            statusNode.className = "text-danger";
            return;
        }

        var months = Math.ceil(gap / monthlyContribution);
        var projectedDate = addMonths(new Date(), months);

        monthsNode.textContent = String(months);
        dateNode.textContent = formatDate.format(projectedDate);

        if (!targetDate) {
            statusNode.textContent = "No target date";
            statusNode.className = "text-muted";
            return;
        }

        if (projectedDate <= targetDate) {
            statusNode.textContent = "On track";
            statusNode.className = "text-success";
        } else {
            statusNode.textContent = "Behind schedule";
            statusNode.className = "text-warning";
        }
    }

    monthlyInput.addEventListener("input", refresh);
    monthlyInput.addEventListener("change", refresh);
    refresh();
}

function addMonths(baseDate, monthsToAdd) {
    var d = new Date(baseDate.getTime());
    var day = d.getDate();
    d.setDate(1);
    d.setMonth(d.getMonth() + monthsToAdd);
    var lastDay = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
    d.setDate(Math.min(day, lastDay));
    return d;
}
