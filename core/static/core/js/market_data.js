const MarketWatchModule = {
    chartsData: [],
    chartInstances: new Map(),

    init: function() {
        this.loadChartData();
        this.bindPeriodLinks();
        this.lazyRenderCharts();
    },

    loadChartData: function() {
        const dataElement = document.getElementById("market-charts-data");
        if (!dataElement) return;

        try {
            const parsed = JSON.parse(dataElement.textContent);
            this.chartsData = Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            this.chartsData = [];
            console.error("Market Watch: invalid charts data payload.", error);
        }
    },

    bindPeriodLinks: function() {
        const links = document.querySelectorAll(".js-period-link");
        if (!links.length) return;

        links.forEach((link) => {
            link.addEventListener("click", () => {
                links.forEach((item) => item.classList.add("disabled"));
                link.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + link.textContent.trim();
            });
        });
    },

    lazyRenderCharts: function() {
        if (!this.chartsData.length) return;

        const cards = document.querySelectorAll("[data-chart-id]");
        if (!cards.length) return;

        if (!("IntersectionObserver" in window)) {
            cards.forEach((card) => this.renderChartFromCard(card));
            return;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) return;
                    this.renderChartFromCard(entry.target);
                    observer.unobserve(entry.target);
                });
            },
            { rootMargin: "220px 0px" }
        );

        cards.forEach((card) => observer.observe(card));
    },

    renderChartFromCard: function(card) {
        const chartId = card.dataset.chartId;
        if (!chartId || this.chartInstances.has(chartId)) return;

        const chartConfig = this.chartsData.find((item) => item.id === chartId);
        const canvas = document.getElementById(chartId);
        if (!chartConfig || !canvas) return;

        const ctx = canvas.getContext("2d");
        const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height || 260);
        gradient.addColorStop(0, this.hexToRgba(chartConfig.color, 0.2));
        gradient.addColorStop(1, this.hexToRgba(chartConfig.color, 0.01));

        const chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: chartConfig.labels,
                datasets: [
                    {
                        label: "Price",
                        data: chartConfig.data,
                        borderColor: chartConfig.color,
                        backgroundColor: gradient,
                        fill: true,
                        borderWidth: 2.2,
                        pointRadius: 0,
                        pointHoverRadius: 3,
                        tension: 0.25,
                        normalized: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                    decimation: {
                        enabled: true,
                        algorithm: "lttb",
                        samples: 120,
                    },
                    tooltip: {
                        backgroundColor: "rgba(15, 23, 42, 0.92)",
                        borderColor: "rgba(148, 163, 184, 0.22)",
                        borderWidth: 1,
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            label: (context) => {
                                const value = Number(context.parsed.y || 0).toLocaleString("de-DE", {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                });
                                return `${chartConfig.currency_symbol}${value}`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: {
                            display: false,
                        },
                        ticks: {
                            maxTicksLimit: 8,
                        },
                    },
                    y: {
                        grid: {
                            color: "rgba(148, 163, 184, 0.15)",
                        },
                        ticks: {
                            callback: (value) => `${chartConfig.currency_symbol}${Number(value).toLocaleString("de-DE")}`,
                        },
                    },
                },
            },
        });

        this.chartInstances.set(chartId, chart);
    },

    hexToRgba: function(hex, opacity) {
        const sanitized = (hex || "").replace("#", "");
        if (sanitized.length !== 6) return `rgba(29, 78, 216, ${opacity})`;

        const bigint = parseInt(sanitized, 16);
        const r = (bigint >> 16) & 255;
        const g = (bigint >> 8) & 255;
        const b = bigint & 255;
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    },
};

document.addEventListener("DOMContentLoaded", () => {
    MarketWatchModule.init();
});
