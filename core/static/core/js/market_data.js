const PortfolioMarketModule = {
    chart: null,
    payload: null,

    init() {
        this.payload = this.readPayload();
        this.renderChart();
        this.bindAssetSearch();
        this.bindLoadingStates();
    },

    readPayload() {
        const dataElement = document.getElementById("market-performance-data");
        if (!dataElement) return null;

        try {
            return JSON.parse(dataElement.textContent);
        } catch (error) {
            console.error("Market Data: invalid chart payload.", error);
            return null;
        }
    },

    renderChart() {
        const canvas = document.getElementById("portfolioMarketChart");
        if (!canvas || !this.payload || !window.Chart) return;

        const labels = this.payload.labels || [];
        const values = this.payload.market_values || [];
        if (!labels.length || !values.length) return;

        const ctx = canvas.getContext("2d");
        const color = this.payload.color || "#2563eb";
        const fill = this.hexToRgba(color, 0.08);

        this.chart = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Market value",
                        data: values,
                        borderColor: color,
                        backgroundColor: fill,
                        borderWidth: 2.4,
                        fill: true,
                        pointRadius: labels.length <= 36 ? 2 : 0,
                        pointHoverRadius: 4,
                        tension: 0.28,
                        normalized: true,
                    },
                    {
                        label: "Capital base",
                        data: this.payload.capital_base_values || [],
                        borderColor: "#64748b",
                        backgroundColor: "transparent",
                        borderDash: [5, 5],
                        borderWidth: 1.8,
                        fill: false,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        tension: 0.12,
                        normalized: true,
                    },
                ],
            },
            options: {
                animation: false,
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: true,
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                        },
                    },
                    decimation: {
                        enabled: true,
                        algorithm: "lttb",
                        samples: 160,
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed.y;
                                return `${context.dataset.label}: ${this.formatCurrency(value)}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            autoSkip: true,
                            maxTicksLimit: 8,
                        },
                    },
                    y: {
                        grid: { color: "rgba(148, 163, 184, 0.16)" },
                        ticks: {
                            callback: (value) => this.formatCompactCurrency(value),
                        },
                    },
                },
            },
        });
    },

    bindAssetSearch() {
        const input = document.getElementById("portfolioAssetSearch");
        const list = document.getElementById("portfolioAssetList");
        const count = document.getElementById("assetSearchCount");
        if (!input || !list) return;

        const options = Array.from(list.querySelectorAll("[data-asset-search]"));
        const sync = () => {
            const terms = input.value
                .toLowerCase()
                .split(/\s+/)
                .map((term) => term.trim())
                .filter(Boolean);
            let visibleAssets = 0;

            options.forEach((option) => {
                const haystack = option.dataset.assetSearch || "";
                const matches = terms.every((term) => haystack.includes(term));
                option.classList.toggle("is-hidden", !matches);
                if (matches && option.dataset.assetKind === "asset") {
                    visibleAssets += 1;
                }
            });

            if (count) {
                count.textContent = String(visibleAssets);
            }
        };

        input.addEventListener("input", sync);
        sync();
    },

    bindLoadingStates() {
        document.querySelectorAll(".market-period-btn, .market-asset-option").forEach((link) => {
            link.addEventListener("click", () => {
                if (link.classList.contains("is-active")) return;
                link.classList.add("is-loading");
                link.setAttribute("aria-busy", "true");
            });
        });
    },

    formatCurrency(value) {
        if (window.FinancialFormatter && typeof window.FinancialFormatter.currency === "function") {
            return window.FinancialFormatter.currency(value);
        }
        return new Intl.NumberFormat("de-DE", {
            style: "currency",
            currency: "EUR",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value || 0);
    },

    formatCompactCurrency(value) {
        const formatter = new Intl.NumberFormat("de-DE", {
            notation: "compact",
            maximumFractionDigits: 1,
        });
        return `${formatter.format(value || 0)}€`;
    },

    hexToRgba(hex, opacity) {
        const sanitized = (hex || "").replace("#", "");
        if (sanitized.length !== 6) return `rgba(37, 99, 235, ${opacity})`;

        const bigint = parseInt(sanitized, 16);
        const r = (bigint >> 16) & 255;
        const g = (bigint >> 8) & 255;
        const b = bigint & 255;
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    },
};

document.addEventListener("DOMContentLoaded", () => {
    PortfolioMarketModule.init();
});

const LiveMarketModule = {
    payload: null,
    chart: null,
    isSelecting: false,
    selectionStartIndex: null,
    selectionEndIndex: null,

    init() {
        this.payload = this.readPayload();
        this.renderChart();
        this.bindRangeSelection();
        this.bindAssetSearch();
        this.bindLoadingStates();
    },

    readPayload() {
        const dataElement = document.getElementById("live-market-data");
        if (!dataElement) return null;

        try {
            return JSON.parse(dataElement.textContent);
        } catch (error) {
            console.error("Live Market Data: invalid chart payload.", error);
            return null;
        }
    },

    renderChart() {
        const canvas = document.getElementById("liveMarketChart");
        if (!canvas || !this.payload || !window.Chart) return;

        const labels = this.payload.labels || [];
        const values = this.payload.data || [];
        if (!labels.length || !values.length) return;

        const ctx = canvas.getContext("2d");
        const color = this.payload.color || "#2563eb";

        this.chart = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: `${this.payload.symbol || "Asset"} price`,
                        data: values,
                        borderColor: color,
                        backgroundColor: this.hexToRgba(color, 0.08),
                        fill: true,
                        borderWidth: 2.4,
                        pointRadius: labels.length <= 36 ? 2 : 0,
                        pointHoverRadius: 4,
                        tension: 0.25,
                        normalized: true,
                    },
                ],
            },
            options: {
                animation: false,
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: true,
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            usePointStyle: true,
                        },
                    },
                    decimation: {
                        enabled: true,
                        algorithm: "lttb",
                        samples: 180,
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `Market price: ${this.formatMarketPrice(context.parsed.y)}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            autoSkip: true,
                            maxTicksLimit: 8,
                        },
                    },
                    y: {
                        grid: { color: "rgba(148, 163, 184, 0.16)" },
                        ticks: {
                            callback: (value) => `${this.payload.currency_symbol || ""}${Number(value).toLocaleString("de-DE")}`,
                        },
                    },
                },
            },
        });
    },

    bindRangeSelection() {
        const canvas = document.getElementById("liveMarketChart");
        if (!canvas || !this.chart || !this.payload) return;

        canvas.style.touchAction = "pan-y";
        canvas.setAttribute("title", "Drag across the chart to measure performance");

        canvas.addEventListener("pointerdown", (event) => {
            const index = this.getIndexForEvent(event);
            if (index === null) return;

            this.isSelecting = true;
            this.selectionStartIndex = index;
            this.selectionEndIndex = index;
            if (canvas.setPointerCapture) {
                canvas.setPointerCapture(event.pointerId);
            }
            this.updateRangeSelection();
            event.preventDefault();
        });

        canvas.addEventListener("pointermove", (event) => {
            if (!this.isSelecting) return;

            const index = this.getIndexForEvent(event);
            if (index === null) return;
            this.selectionEndIndex = index;
            this.updateRangeSelection();
            event.preventDefault();
        });

        const finishSelection = (event) => {
            if (!this.isSelecting) return;
            this.isSelecting = false;
            if (canvas.releasePointerCapture) {
                try {
                    canvas.releasePointerCapture(event.pointerId);
                } catch (error) {
                    // Pointer capture can already be released by the browser.
                }
            }
            this.updateRangeSelection();
        };

        canvas.addEventListener("pointerup", finishSelection);
        canvas.addEventListener("pointercancel", finishSelection);
        window.addEventListener("resize", () => this.updateRangeSelection());
    },

    getIndexForEvent(event) {
        const labels = this.payload.labels || [];
        if (!labels.length || !this.chart || !this.chart.scales || !this.chart.scales.x) {
            return null;
        }

        const rect = this.chart.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const rawValue = this.chart.scales.x.getValueForPixel(x);
        const numericValue = Number(rawValue);
        if (!Number.isFinite(numericValue)) {
            return null;
        }

        const index = Math.round(numericValue);
        return Math.max(0, Math.min(labels.length - 1, index));
    },

    updateRangeSelection() {
        const overlay = document.getElementById("liveMarketRangeOverlay");
        const summary = document.getElementById("liveMarketRangeSummary");
        if (!overlay || !summary || !this.chart || this.selectionStartIndex === null || this.selectionEndIndex === null) {
            return;
        }

        const startIndex = Math.min(this.selectionStartIndex, this.selectionEndIndex);
        const endIndex = Math.max(this.selectionStartIndex, this.selectionEndIndex);
        if (startIndex === endIndex) {
            overlay.classList.remove("is-visible");
            summary.hidden = true;
            return;
        }

        const xScale = this.chart.scales.x;
        const chartArea = this.chart.chartArea;
        const labels = this.payload.labels || [];
        const canvasRect = this.chart.canvas.getBoundingClientRect();
        const shellRect = this.chart.canvas.parentElement.getBoundingClientRect();
        const startPixel = xScale.getPixelForValue(labels[startIndex], startIndex);
        const endPixel = xScale.getPixelForValue(labels[endIndex], endIndex);
        const left = canvasRect.left - shellRect.left + Math.min(startPixel, endPixel);
        const width = Math.abs(endPixel - startPixel);

        overlay.style.left = `${left}px`;
        overlay.style.top = `${canvasRect.top - shellRect.top + chartArea.top}px`;
        overlay.style.width = `${width}px`;
        overlay.style.height = `${chartArea.bottom - chartArea.top}px`;
        overlay.classList.add("is-visible");

        this.renderRangeSummary(summary, startIndex, endIndex);
    },

    renderRangeSummary(summary, startIndex, endIndex) {
        const values = this.payload.data || [];
        const labels = this.payload.labels || [];
        const startValue = Number(values[startIndex]);
        const endValue = Number(values[endIndex]);
        if (!Number.isFinite(startValue) || !Number.isFinite(endValue)) {
            summary.hidden = true;
            return;
        }

        const changeAbs = endValue - startValue;
        const changePct = startValue ? (changeAbs / startValue) * 100 : 0;
        const performance = summary.querySelector("[data-range-performance]");
        const detail = summary.querySelector("[data-range-detail]");
        const prefix = changePct >= 0 ? "+" : "";

        if (performance) {
            performance.textContent = `${prefix}${changePct.toFixed(2)}%`;
        }
        if (detail) {
            detail.textContent = `${labels[startIndex]} to ${labels[endIndex]} | ${this.formatMarketPrice(startValue)} to ${this.formatMarketPrice(endValue)} (${this.formatSignedPrice(changeAbs)})`;
        }

        summary.classList.toggle("is-up", changeAbs >= 0);
        summary.classList.toggle("is-down", changeAbs < 0);
        summary.hidden = false;
    },

    bindAssetSearch() {
        const input = document.querySelector("[data-market-search-input]");
        const list = document.getElementById("portfolioAssetList");
        const count = document.getElementById("assetSearchCount");
        if (!input || !list) return;

        const options = Array.from(list.querySelectorAll("[data-asset-search]"));
        const sync = () => {
            const terms = input.value
                .toLowerCase()
                .split(/\s+/)
                .map((term) => term.trim())
                .filter(Boolean);
            let visibleAssets = 0;

            options.forEach((option) => {
                const haystack = option.dataset.assetSearch || "";
                const matches = terms.every((term) => haystack.includes(term));
                option.classList.toggle("is-hidden", !matches);
                if (matches && option.dataset.assetKind === "asset") {
                    visibleAssets += 1;
                }
            });

            if (count) {
                count.textContent = String(visibleAssets);
            }
        };

        input.addEventListener("input", sync);
        sync();
    },

    bindLoadingStates() {
        document.querySelectorAll(".market-period-btn, .market-asset-option").forEach((link) => {
            link.addEventListener("click", () => {
                if (link.classList.contains("is-active")) return;
                link.classList.add("is-loading");
                link.setAttribute("aria-busy", "true");
            });
        });
    },

    formatMarketPrice(value) {
        const amount = Number(value || 0).toLocaleString("de-DE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return `${this.payload.currency_symbol || ""}${amount}`;
    },

    formatSignedPrice(value) {
        const prefix = value >= 0 ? "+" : "-";
        return `${prefix}${this.formatMarketPrice(Math.abs(value))}`;
    },

    hexToRgba(hex, opacity) {
        const sanitized = (hex || "").replace("#", "");
        if (sanitized.length !== 6) return `rgba(37, 99, 235, ${opacity})`;

        const bigint = parseInt(sanitized, 16);
        const r = (bigint >> 16) & 255;
        const g = (bigint >> 8) & 255;
        const b = bigint & 255;
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    },
};

document.addEventListener("DOMContentLoaded", () => {
    LiveMarketModule.init();
});
