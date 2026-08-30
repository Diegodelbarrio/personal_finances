/**
 * FinOrbit - Core Global JavaScript
 * Gestiona formateadores, componentes comunes y configuraciones de librerías.
 */

// 1. FORMATEADORES GLOBALES (Accesibles desde cualquier script)
const FinancialFormatter = {
    locale: document.documentElement.lang === 'es' ? 'es-ES' : 'en-GB',
    currencyCode: document.documentElement.dataset.currency || 'EUR',
    currency: (val, options = {}) => {
        const numericValue = val === null || val === undefined ? 0 : Number(val);
        return new Intl.NumberFormat(FinancialFormatter.locale, {
            style: 'currency', 
            currency: FinancialFormatter.currencyCode,
            minimumFractionDigits: 2,
            ...options
        }).format(numericValue);
    },
    // Formatea a porcentaje: 0.1234 -> 12.3%
    percentage: (val) => {
        if (val === null || val === undefined) return '0%';
        return (val).toFixed(1) + '%';
    },
    // Formatea números simples con separador de miles
    number: (val) => {
        return new Intl.NumberFormat(FinancialFormatter.locale).format(val);
    }
};

// 2. CONFIGURACIÓN GLOBAL DE CHART.JS (Si la librería está cargada)
if (window.Chart) {
    Chart.defaults.font.family = "'Inter', 'system-ui', sans-serif";
    Chart.defaults.color = '#64748b'; // Color del texto de ejes
    Chart.defaults.plugins.tooltip.backgroundColor = '#1e293b';
    Chart.defaults.plugins.tooltip.titleFont = { weight: 'bold' };
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
}

// 3. COMPORTAMIENTO DE LA BARRA DE NAVEGACIÓN (SCROLL & MOBILE MENU)
document.addEventListener('DOMContentLoaded', () => {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    const SCROLL_THRESHOLD = 30;
    const syncNavbarScrollState = () => {
        navbar.classList.toggle('scrolled', window.scrollY > SCROLL_THRESHOLD);
    };

    syncNavbarScrollState();
    window.addEventListener('scroll', syncNavbarScrollState, { passive: true });

    // Detectar apertura del menú móvil para poner fondo sólido
    const navCollapse = navbar.querySelector('.navbar-collapse');
    if (navCollapse) {
        navCollapse.addEventListener('show.bs.collapse', () => {
            navbar.classList.add('navbar-expanded');
        });
        navCollapse.addEventListener('hide.bs.collapse', () => {
            navbar.classList.remove('navbar-expanded');
        });
    }
});



/**
 * ChartFactory - Motor de gráficos interactivos de FinOrbit
 */
const ChartFactory = {
    // defaultPalette: ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#858796' , '#5a5c69', '#e74a3b'],
    defaultPalette: [
        '#4F46E5', // Indigo (Principal / Patrimonio)
        '#10B981', // Emerald (Ingresos / Cuentas Corrientes)
        '#36b9cc', // Sky Blue (Inversiones / ETFs)
        '#F59E0B', // Amber (Ahorro / Fondos)
        '#8B5CF6', // Violet (Cripto / Otros)
        '#F43F5E', // Rose (Gastos / Pasivos)
        '#64748B'  // Slate (Neutral / Metales)
    ],

    createInteractiveDonut: function(canvasId, legendId, labels, values, customColors = null) {
        const ctx = document.getElementById(canvasId);
        const legendContainer = document.getElementById(legendId);
        const colors = customColors || this.defaultPalette;
        
        if (!ctx || !legendContainer || !values || values.length === 0) return;

        // 1. Preparar y ordenar datos (Lógica de Finances)
        let chartData = labels.map((label, i) => ({
            label: label,
            value: values[i],
            color: colors[i % colors.length]
        })).sort((a, b) => b.value - a.value);

        const total = chartData.reduce((a, b) => a + b.value, 0);

        // 2. Crear Gráfico
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartData.map(d => d.label),
                datasets: [{
                    data: chartData.map(d => d.value),
                    backgroundColor: chartData.map(d => d.color),
                    cutout: '50%', // Un poco más fino para un look más moderno
                    borderColor: '#fff',
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => ` ${FinancialFormatter.currency(context.raw)}`
                        }
                    }
                },
                onHover: (event, chartElement) => {
                    const legendItems = legendContainer.querySelectorAll('.legend-card');
                    legendItems.forEach(el => { el.classList.remove('active'); });
                    
                    if (chartElement.length > 0) {
                        const index = chartElement[0].index;
                        if (legendItems[index]) legendItems[index].classList.add('active');
                    }
                }
            }
        });

        // 3. Generar Leyenda (Usando FinancialFormatter y clases CSS)
        legendContainer.innerHTML = '';
        chartData.forEach((item, i) => {
            const percentage = total > 0 ? ((item.value / total) * 100).toFixed(1) : 0;
            const card = document.createElement('div');
            card.className = 'legend-card';
            card.style.cursor = 'pointer';

            const colorDot = document.createElement('div');
            colorDot.style.width = '8px';
            colorDot.style.height = '8px';
            colorDot.style.borderRadius = '50%';
            colorDot.style.backgroundColor = item.color;
            colorDot.style.flexShrink = '0';

            const content = document.createElement('div');
            content.className = 'ms-2 flex-grow-1 d-flex justify-content-between align-items-center';

            const details = document.createElement('div');
            const label = document.createElement('div');
            label.className = 'fw-bold';
            label.style.fontSize = '0.8rem';
            label.textContent = String(item.label ?? '');

            const value = document.createElement('div');
            value.className = 'text-muted';
            value.style.fontSize = '0.65rem';
            value.textContent = FinancialFormatter.currency(Number(item.value || 0));

            const percent = document.createElement('div');
            percent.className = 'fw-bold';
            percent.style.fontSize = '0.85rem';
            percent.textContent = `${percentage}%`;

            details.append(label, value);
            content.append(details, percent);
            card.append(colorDot, content);

            card.onmouseenter = () => {
                chart.setActiveElements([{ datasetIndex: 0, index: i }]);
                chart.tooltip.setActiveElements([{ datasetIndex: 0, index: i }], { x: 0, y: 0 });
                chart.update();
            };
            card.onmouseleave = () => {
                chart.setActiveElements([]);
                chart.update();
            };
            legendContainer.appendChild(card);
        });

        return chart;
    },

    createStackedBarChart: function(canvasId, labels, datasetsRaw) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: datasetsRaw.map((ds, i) => ({
                    ...ds,
                    backgroundColor: this.defaultPalette[i % this.defaultPalette.length],
                    borderRadius: 0,
                    borderSkipped: false,
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { 
                        display: true, 
                        position: 'bottom', 
                        labels: { boxWidth: 12, usePointStyle: true, font: { size: 11 } } 
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${FinancialFormatter.currency(ctx.parsed.y)}`
                        }
                    }
                },
                scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: { 
                        stacked: true, 
                        beginAtZero: true,
                        ticks: { callback: v => FinancialFormatter.currency(v) }
                    }
                }
            }
        });
    }
};

/**
 * Función auxiliar para logs de depuración en desarrollo
 */
const FinLog = (message, data = null) => {
    if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
        data ? console.log(`[FinOrbit] ${message}`, data) : console.log(`[FinOrbit] ${message}`);
    }
};


/**
 * FinOrbit Dropdown Manager
 * Maneja el comportamiento hover de forma eficiente
 */
const DropdownHandler = {
    listeners: [],
    hoverMediaQuery: window.matchMedia('(min-width: 992px) and (hover: hover) and (pointer: fine)'),

    init() {
        if (!window.bootstrap || !window.bootstrap.Dropdown) return;
        this.hoverDropdowns = Array.from(document.querySelectorAll('.dropdown-hover'));
        if (!this.hoverDropdowns.length) return;

        this.hoverDropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.dropdown-toggle[href="#"]');
            if (!toggle || toggle.dataset.preventNavBound === 'true') return;
            toggle.dataset.preventNavBound = 'true';
            toggle.addEventListener('click', (event) => event.preventDefault());
        });

        this.applyInteractionMode();

        if (!this._boundViewportListener) {
            this._boundViewportListener = () => this.applyInteractionMode();
            if (this.hoverMediaQuery.addEventListener) {
                this.hoverMediaQuery.addEventListener('change', this._boundViewportListener);
            } else {
                this.hoverMediaQuery.addListener(this._boundViewportListener);
            }
        }
    },

    applyInteractionMode() {
        this.teardown();

        // En móvil/touch dejamos sólo click para evitar cierres accidentales.
        if (!this.hoverMediaQuery.matches) {
            this.closeAll();
            return;
        }

        this.hoverDropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.dropdown-toggle');
            const menu = dropdown.querySelector('.dropdown-menu');
            if (!toggle) return;

            const instance = bootstrap.Dropdown.getOrCreateInstance(toggle);
            let openTimer = null;
            let closeTimer = null;

            const clearTimers = () => {
                clearTimeout(openTimer);
                clearTimeout(closeTimer);
            };

            const openDropdown = () => {
                clearTimeout(closeTimer);
                openTimer = setTimeout(() => {
                    this.closeAll(dropdown);
                    instance.show();
                }, 0);
            };

            const closeDropdown = (event) => {
                if (event && dropdown.contains(event.relatedTarget)) return;
                clearTimeout(openTimer);
                closeTimer = setTimeout(() => {
                    instance.hide();
                }, 100);
            };

            const focusOutHandler = (event) => {
                if (!dropdown.contains(event.relatedTarget)) {
                    closeDropdown();
                }
            };

            const escapeHandler = (event) => {
                if (event.key === 'Escape') {
                    clearTimers();
                    instance.hide();
                    toggle.focus();
                }
            };

            dropdown.addEventListener('mouseenter', openDropdown);
            dropdown.addEventListener('mouseleave', closeDropdown);
            dropdown.addEventListener('focusin', openDropdown);
            dropdown.addEventListener('focusout', focusOutHandler);
            dropdown.addEventListener('keydown', escapeHandler);
            if (menu) {
                menu.addEventListener('mouseenter', openDropdown);
                menu.addEventListener('mouseleave', closeDropdown);
            }

            this.listeners.push({
                dropdown,
                menu,
                openDropdown,
                closeDropdown,
                focusOutHandler,
                escapeHandler,
                clearTimers
            });
        });
    },

    teardown() {
        this.listeners.forEach(({ dropdown, menu, openDropdown, closeDropdown, focusOutHandler, escapeHandler, clearTimers }) => {
            dropdown.removeEventListener('mouseenter', openDropdown);
            dropdown.removeEventListener('mouseleave', closeDropdown);
            dropdown.removeEventListener('focusin', openDropdown);
            dropdown.removeEventListener('focusout', focusOutHandler);
            dropdown.removeEventListener('keydown', escapeHandler);
            if (menu) {
                menu.removeEventListener('mouseenter', openDropdown);
                menu.removeEventListener('mouseleave', closeDropdown);
            }
            clearTimers();
        });
        this.listeners = [];
    },

    closeAll(exceptDropdown = null) {
        const openToggles = document.querySelectorAll('.dropdown-hover > .dropdown-toggle.show');
        openToggles.forEach(toggle => {
            if (exceptDropdown && exceptDropdown.contains(toggle)) return;
            const inst = bootstrap.Dropdown.getInstance(toggle);
            if (inst) inst.hide();
        });
    }
};

document.addEventListener("DOMContentLoaded", () => DropdownHandler.init());
