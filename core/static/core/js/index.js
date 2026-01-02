/**
 * Lógica para el Dashboard principal (Index)
 */
document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. GRÁFICO DE NET WORTH ---
    const chartCanvas = document.getElementById('netWorthChart');
    const dataContainer = document.getElementById('net-worth-data');
    

    // Solo ejecutamos si ambos elementos existen en el DOM
    if (chartCanvas && dataContainer) {
        try {
            const ctx = chartCanvas.getContext('2d');
            const rawData = JSON.parse(dataContainer.textContent);
            console.log("Datos recibidos:", rawData);
            if (rawData && rawData.length > 0) {
                const labels = rawData.map(item => item.label);
                const savingsValues = rawData.map(item => item.savings);
                const investmentValues = rawData.map(item => item.investments);

                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels,
                        datasets: [
                            {
                                label: ' Savings & Cash',
                                data: savingsValues,
                                fill: true,
                                backgroundColor: 'rgba(25, 135, 84, 0.15)',
                                borderColor: '#198754',
                                borderWidth: 2,
                                tension: 0.4,
                                pointRadius: 0,
                                pointHoverRadius: 6,
                            },
                            {
                                label: ' Investments',
                                data: investmentValues,
                                fill: true,
                                backgroundColor: 'rgba(13, 110, 253, 0.15)',
                                borderColor: '#0d6efd',
                                borderWidth: 2,
                                tension: 0.4,
                                pointRadius: 0,
                                pointHoverRadius: 6,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                align: 'end',
                                labels: {
                                    boxWidth: 8,
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    font: { size: 11, weight: 'bold' }
                                }
                            },
                            tooltip: {
                                padding: 12,
                                callbacks: {
                                    label: (context) => ` ${context.dataset.label}: ${context.parsed.y.toLocaleString('de-DE')} €`,
                                    footer: (tooltipItems) => {
                                        let sum = 0;
                                        tooltipItems.forEach(i => sum += i.parsed.y);
                                        return 'TOTAL: ' + sum.toLocaleString('de-DE') + ' €';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { grid: { display: false } },
                            y: {
                                stacked: true,
                                beginAtZero: true,
                                ticks: {
                                    callback: v => v.toLocaleString('de-DE') + ' €'
                                }
                            }
                        }
                    }
                });
            }
        } catch (e) {
            console.error("Error rendering Chart.js:", e);
        }
    }

    // --- 2. BARRAS DE PROGRESO (Efecto Carga) ---
    const progressBars = document.querySelectorAll('.js-progress'); // Usamos tu nueva clase
    progressBars.forEach(bar => {
        // Leemos el valor del atributo data-value que viene de Django
        const targetValue = bar.getAttribute('data-value');
        
        if (targetValue) {
            // Mantenemos el timeout para que se vea la animación al cargar
            setTimeout(() => {
                bar.style.width = targetValue + '%';
            }, 150); 
        }
    });

    // --- 3. BOOTSTRAP TOOLTIPS ---
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});