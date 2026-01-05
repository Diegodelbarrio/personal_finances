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
                
                // --- CÁLCULO DE PORCENTAJES (Breakdown) con Fallback ---
                // Detectamos si el estado global no es "ok" (warning o danger)
                const badge = document.querySelector('.status-badge');
                const isNotOk = badge?.classList.contains('status-danger') || badge?.classList.contains('status-warning');
                
                let breakdownEntry = rawData[rawData.length - 1];
                
                // Si hay historial y el mes actual parece incompleto o está marcado como stale,
                // usamos los datos del mes anterior para el indicador de porcentajes.
                if (rawData.length > 1) {
                    const prevEntry = rawData[rawData.length - 2];
                    const isIncomplete = (breakdownEntry.savings === 0 && prevEntry.savings > 0) || 
                                        (breakdownEntry.investments === 0 && prevEntry.investments > 0);
                    
                    if (isNotOk || isIncomplete) {
                        breakdownEntry = prevEntry;
                    }
                }

                const total = breakdownEntry.savings + breakdownEntry.investments;
                
                if (total > 0) {
                    const cashPct = ((breakdownEntry.savings / total) * 100).toFixed(1);
                    const invPct = (100 - parseFloat(cashPct)).toFixed(1); // Para que sumen 100 exacto

                    const cashBar = document.getElementById('cash-bar');
                    const invBar = document.getElementById('investments-bar');
                    const cashText = document.getElementById('cash-percentage');
                    const invText = document.getElementById('investments-percentage');

                    if (cashBar) cashBar.style.width = cashPct + '%';
                    if (invBar) invBar.style.width = invPct + '%';
                    if (cashText) cashText.textContent = cashPct + '%';
                    if (invText) invText.textContent = invPct + '%';

                    // Actualizamos el atributo title para que el tooltip muestre el valor real en euros
                    if (cashBar) cashBar.title = `Cash: ${breakdownEntry.savings.toLocaleString('de-DE')} €`;
                    if (invBar) invBar.title = `Investments: ${breakdownEntry.investments.toLocaleString('de-DE')} €`;
                }

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