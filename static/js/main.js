/**
 * FinOrbit - Core Global JavaScript
 * Gestiona formateadores, componentes comunes y configuraciones de librerías.
 */

// 1. FORMATEADORES GLOBALES (Accesibles desde cualquier script)
const FinancialFormatter = {
    // Formatea números a moneda Euro: 1234.5 -> 1.234,50 €
    currency: (val) => {
        if (val === null || val === undefined) return '0,00 €';
        return new Intl.NumberFormat('de-DE', { 
            style: 'currency', 
            currency: 'EUR',
            minimumFractionDigits: 2 
        }).format(val);
    },
    // Formatea a porcentaje: 0.1234 -> 12.3%
    percentage: (val) => {
        if (val === null || val === undefined) return '0%';
        return (val).toFixed(1) + '%';
    },
    // Formatea números simples con separador de miles
    number: (val) => {
        return new Intl.NumberFormat('de-DE').format(val);
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

// 3. COMPORTAMIENTO DE LA BARRA DE NAVEGACIÓN AL HACER SCROLL
document.addEventListener('DOMContentLoaded', () => {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    const SCROLL_THRESHOLD = 30;

    window.addEventListener('scroll', () => {
        navbar.classList.toggle('scrolled', window.scrollY > SCROLL_THRESHOLD);
    });
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
            card.innerHTML = `
                <div style="width:8px; height:8px; border-radius:50%; background:${item.color}; flex-shrink:0;"></div>
                <div class="ms-2 flex-grow-1 d-flex justify-content-between align-items-center">
                    <div>
                        <div class="fw-bold" style="font-size:0.8rem;">${item.label}</div>
                        <div class="text-muted" style="font-size:0.65rem;">${item.value.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €</div>
                    </div>
                    <div class="fw-bold" style="font-size:0.85rem;">${percentage}%</div>
                </div>`;

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
    init() {
        const hoverDropdowns = document.querySelectorAll('.dropdown-hover');
        
        hoverDropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.dropdown-toggle');
            // Creamos la instancia una sola vez y la guardamos
            const instance = bootstrap.Dropdown.getOrCreateInstance(toggle);
            let timeout = null;

            dropdown.addEventListener('mouseenter', () => {
                clearTimeout(timeout);
                // Cerramos otros dropdowns abiertos si los hubiera
                this.closeAll();
                instance.show();
            });

            dropdown.addEventListener('mouseleave', () => {
                timeout = setTimeout(() => {
                    instance.hide();
                }, 150);
            });
        });
    },

    closeAll() {
        const openMenus = document.querySelectorAll('.dropdown-hover .show');
        openMenus.forEach(menu => {
            const toggle = menu.parentElement.querySelector('.dropdown-toggle');
            const inst = bootstrap.Dropdown.getInstance(toggle);
            if (inst) inst.hide();
        });
    }
};

document.addEventListener("DOMContentLoaded", () => DropdownHandler.init());