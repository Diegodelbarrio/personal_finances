/**
 * Investments Module Logic - Versión Integrada y Corregida
 */
const InvestmentsModule = {
    init: function() {
        this.setupPerformanceChart(); 
        this.setupAllocationDonut();  
        this.setupContributionsChart(); 
        this.setupDataTable();
        this.animateProgressBars(); // Nueva función para las barras de progreso
    },

    setupAllocationDonut: function() {
        const labelsEl = document.getElementById('allocation-labels');
        const valuesEl = document.getElementById('allocation-data');
        if (!labelsEl || !valuesEl) return;

        const labels = JSON.parse(labelsEl.textContent);
        const values = JSON.parse(valuesEl.textContent);

        ChartFactory.createInteractiveDonut(
            'allocationChart', 
            'allocationLegend', 
            labels, 
            values
        );
    },

    setupPerformanceChart: function() {
        const el = document.getElementById('performanceChart');
        if (!el) return;
        const data = JSON.parse(document.getElementById('performance-data').textContent);
        
        new Chart(el, {
            type: 'line',
            data: {
                labels: data.map(d => d.label),
                datasets: [
                    {
                        label: 'Market Value',
                        data: data.map(d => d.market),
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointRadius: 2
                    },
                    {
                        label: 'Invested',
                        data: data.map(d => d.invested),
                        borderColor: '#adb5bd',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0,
                        borderWidth: 2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: true, position: 'bottom' }
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { 
                        beginAtZero: true,
                        ticks: { callback: (v) => FinancialFormatter.currency(v) } 
                    }
                }
            }
        });
    },

    // 2. CORRECCIÓN PRINCIPAL: Ahora usa el motor global de Barras
    setupContributionsChart: function() {
        const labelsEl = document.getElementById('bar-labels');
        const dataEl = document.getElementById('bar-datasets');
        
        if (!labelsEl || !dataEl) return;

        // Llamada globalizada: elimina +50 líneas de configuración repetida
        ChartFactory.createStackedBarChart(
            'monthlyContributionsChart', 
            JSON.parse(labelsEl.textContent), 
            JSON.parse(dataEl.textContent)
        );
    },

    setupDataTable: function() {
        const tableEl = $('#portfolioTable');
        if ($.fn.DataTable && tableEl.length) {
            // Inicializar DataTable con la lógica de estilo antigua
            const table = tableEl.DataTable({
                pageLength: 25,
                order: [[4, 'desc']],
                language: { search: "", searchPlaceholder: "Search asset..." },
                dom: '<"d-flex justify-content-between align-items-center mb-3"f>rt<"d-flex justify-content-between align-items-center p-3"ip>'
            });

            // Mover el buscador al contenedor específico si existe en el HTML
            const searchContainer = $('#searchContainer');
            if (searchContainer.length) {
                searchContainer.append($('.dataTables_filter'));
            }
        }
    },

    animateProgressBars: function() {
        // Recuperamos la lógica de animación de las barras de progreso de la tabla
        setTimeout(() => {
            document.querySelectorAll('.progress-bar').forEach(bar => {
                if (bar.dataset.width) {
                    bar.style.width = bar.dataset.width;
                }
            });
        }, 300); // Pequeño delay para asegurar que el DOM de la tabla esté listo
    }
};

$(document).ready(function() {
    InvestmentsModule.init();
});