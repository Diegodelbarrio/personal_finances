/**
 * Lógica para el Dashboard principal (Index)
 */
document.addEventListener('DOMContentLoaded', () => {
    const formatCurrency = (value, digits = 0) => {
        if (window.FinancialFormatter) {
            return FinancialFormatter.currency(value, {
                minimumFractionDigits: digits,
                maximumFractionDigits: digits
            });
        }
        const amount = Number(value) || 0;
        return amount.toLocaleString(document.documentElement.lang || 'en-GB', {
            style: 'currency',
            currency: document.documentElement.dataset.currency || 'EUR',
            minimumFractionDigits: digits,
            maximumFractionDigits: digits
        });
    };

    const formatSignedCurrency = (value) => {
        const amount = Number(value) || 0;
        const sign = amount >= 0 ? '+' : '-';
        return `${sign}${formatCurrency(Math.abs(amount), 0)}`;
    };

    const updateDeltaTone = (node, value) => {
        if (!node) return;
        node.classList.remove('is-positive', 'is-negative');
        if (value > 0) node.classList.add('is-positive');
        if (value < 0) node.classList.add('is-negative');
    };
    
    // --- 1. GRÁFICO DE NET WORTH ---
    const chartCanvas = document.getElementById('netWorthChart');
    const dataContainer = document.getElementById('net-worth-data');
    

    // Solo ejecutamos si ambos elementos existen en el DOM
    if (chartCanvas && dataContainer) {
        try {
            const ctx = chartCanvas.getContext('2d');
            const rawData = JSON.parse(dataContainer.textContent);
            if (rawData && rawData.length > 0) {
                const normalizedData = rawData.map(item => ({
                    label: item.label || '',
                    savings: Number(item.savings) || 0,
                    investments: Number(item.investments) || 0
                }));

                // Detectamos si el estado global no es "ok" (warning o danger)
                const badge = document.querySelector('.js-net-worth-status');
                const isNotOk = badge?.classList.contains('status-danger') || badge?.classList.contains('status-warning');

                const cashBar = document.getElementById('cash-bar');
                const invBar = document.getElementById('investments-bar');
                const cashText = document.getElementById('cash-percentage');
                const invText = document.getElementById('investments-percentage');
                const totalText = document.getElementById('nw-total-value');
                const cashValueText = document.getElementById('nw-cash-value');
                const invValueText = document.getElementById('nw-investments-value');
                const rangeLabel = document.getElementById('nw-range-label');
                const monthlyDeltaNode = document.getElementById('nw-monthly-delta');
                const monthlyRateNode = document.getElementById('nw-monthly-delta-rate');
                const periodDeltaNode = document.getElementById('nw-period-delta');
                const periodRateNode = document.getElementById('nw-period-delta-rate');
                const dominantAssetNode = document.getElementById('nw-dominant-asset');
                const dominantShareNode = document.getElementById('nw-dominant-share');
                const rangeWindowNode = document.getElementById('nw-range-window');
                const rangeStartInput = document.getElementById('nw-range-start');
                const rangeEndInput = document.getElementById('nw-range-end');
                const rangeFill = document.getElementById('nw-range-fill');
                const rangeSliderBlock = document.querySelector('.js-nw-range-slider-block');

                const maxIndex = normalizedData.length - 1;
                const minGap = maxIndex > 0 ? 1 : 0;

                const updateRangeFill = (startIndex, endIndex) => {
                    if (!rangeFill) return;
                    if (maxIndex <= 0) {
                        rangeFill.style.left = '0%';
                        rangeFill.style.width = '100%';
                        return;
                    }

                    const left = (startIndex / maxIndex) * 100;
                    const right = (endIndex / maxIndex) * 100;
                    rangeFill.style.left = `${left}%`;
                    rangeFill.style.width = `${Math.max(right - left, 0)}%`;
                };

                const legendBottomSpacingPlugin = {
                    id: 'legendBottomSpacingPlugin',
                    beforeUpdate: (chart) => {
                        const legend = chart.legend;
                        if (!legend || legend.$extraBottomSpaceApplied) return;
                        const originalFit = legend.fit;
                        legend.fit = function fit() {
                            originalFit.bind(this)();
                            this.height += 18;
                        };
                        legend.$extraBottomSpaceApplied = true;
                    }
                };

                const gradientHeight = chartCanvas.clientHeight || 320;
                const savingsGradient = ctx.createLinearGradient(0, 0, 0, gradientHeight);
                savingsGradient.addColorStop(0, 'rgba(15, 118, 110, 0.2)');
                savingsGradient.addColorStop(1, 'rgba(15, 118, 110, 0.03)');

                const investmentsGradient = ctx.createLinearGradient(0, 0, 0, gradientHeight);
                investmentsGradient.addColorStop(0, 'rgba(36, 84, 214, 0.2)');
                investmentsGradient.addColorStop(1, 'rgba(36, 84, 214, 0.03)');

                const netWorthChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: normalizedData.map(item => item.label),
                        datasets: [
                            {
                                label: 'Cash',
                                data: normalizedData.map(item => item.savings),
                                stack: 'networth',
                                fill: true,
                                backgroundColor: savingsGradient,
                                borderColor: '#0f766e',
                                borderWidth: 2,
                                tension: 0.35,
                                pointRadius: 0,
                                pointHoverRadius: 4,
                            },
                            {
                                label: 'Investments',
                                data: normalizedData.map(item => item.investments),
                                stack: 'networth',
                                fill: '-1',
                                backgroundColor: investmentsGradient,
                                borderColor: '#2454d6',
                                borderWidth: 2,
                                tension: 0.35,
                                pointRadius: 0,
                                pointHoverRadius: 4,
                            }
                        ]
                    },
                    plugins: [legendBottomSpacingPlugin],
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top',
                                align: 'start',
                                labels: {
                                    boxWidth: 9,
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    color: '#344054',
                                    padding: 12,
                                    font: { size: 10, weight: 'bold' }
                                }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(15, 23, 42, 0.92)',
                                borderColor: 'rgba(148, 163, 184, 0.32)',
                                borderWidth: 1,
                                padding: 12,
                                callbacks: {
                                    label: (context) => ` ${context.dataset.label}: ${formatCurrency(context.raw)}`,
                                    footer: (tooltipItems) => {
                                        const dataIndex = tooltipItems?.[0]?.dataIndex;
                                        const tooltipChart = tooltipItems?.[0]?.chart;
                                        if (typeof dataIndex === 'number' && tooltipChart) {
                                            const cash = Number(tooltipChart.data.datasets[0].data[dataIndex]) || 0;
                                            const investments = Number(tooltipChart.data.datasets[1].data[dataIndex]) || 0;
                                            return `TOTAL: ${formatCurrency(cash + investments)}`;
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { display: false },
                                ticks: {
                                    color: '#667085',
                                    maxRotation: 0,
                                    autoSkip: true,
                                    font: { size: 10 }
                                }
                            },
                            y: {
                                stacked: true,
                                beginAtZero: true,
                                grid: {
                                    color: 'rgba(152, 162, 179, 0.2)',
                                    drawBorder: false
                                },
                                ticks: {
                                    color: '#667085',
                                    font: { size: 10 },
                                    callback: v => formatCurrency(v)
                                }
                            }
                        }
                    }
                });

                const renderWindow = (startIndex, endIndex) => {
                    const windowData = normalizedData.slice(startIndex, endIndex + 1);
                    if (!windowData.length) return;

                    const labels = windowData.map(item => item.label);
                    const savingsValues = windowData.map(item => item.savings);
                    const investmentValues = windowData.map(item => item.investments);
                    const totalValues = windowData.map(item => item.savings + item.investments);

                    let breakdownIndex = windowData.length - 1;
                    if (windowData.length > 1) {
                        const currentEntry = windowData[breakdownIndex];
                        const prevEntry = windowData[breakdownIndex - 1];
                        const isIncomplete = (currentEntry.savings === 0 && prevEntry.savings > 0) ||
                            (currentEntry.investments === 0 && prevEntry.investments > 0);
                        const shouldApplyStaleFallback = isNotOk && endIndex === maxIndex;
                        if (shouldApplyStaleFallback || isIncomplete) {
                            breakdownIndex -= 1;
                        }
                    }

                    breakdownIndex = Math.max(0, breakdownIndex);
                    const breakdownEntry = windowData[breakdownIndex];
                    const selectedTotal = (breakdownEntry.savings + breakdownEntry.investments) || 0;

                    let cashPctValue = 0;
                    let invPctValue = 0;
                    if (selectedTotal > 0) {
                        cashPctValue = (breakdownEntry.savings / selectedTotal) * 100;
                        invPctValue = 100 - cashPctValue;
                    }

                    if (cashBar) {
                        cashBar.style.width = `${cashPctValue}%`;
                        cashBar.title = `Cash: ${formatCurrency(breakdownEntry.savings)}`;
                        cashBar.setAttribute('aria-valuemin', '0');
                        cashBar.setAttribute('aria-valuemax', '100');
                        cashBar.setAttribute('aria-valuenow', cashPctValue.toFixed(1));
                    }

                    if (invBar) {
                        invBar.style.width = `${invPctValue}%`;
                        invBar.title = `Investments: ${formatCurrency(breakdownEntry.investments)}`;
                        invBar.setAttribute('aria-valuemin', '0');
                        invBar.setAttribute('aria-valuemax', '100');
                        invBar.setAttribute('aria-valuenow', invPctValue.toFixed(1));
                    }

                    if (cashText) cashText.textContent = `${cashPctValue.toFixed(1)}%`;
                    if (invText) invText.textContent = `${invPctValue.toFixed(1)}%`;
                    if (totalText) totalText.textContent = formatCurrency(selectedTotal);
                    if (cashValueText) cashValueText.textContent = formatCurrency(breakdownEntry.savings);
                    if (invValueText) invValueText.textContent = formatCurrency(breakdownEntry.investments);

                    const rangeText = labels.length > 1
                        ? `${labels[0]} - ${labels[labels.length - 1]}`
                        : (labels[0] || 'Single data point');

                    if (rangeLabel) rangeLabel.textContent = rangeText;
                    if (rangeWindowNode) rangeWindowNode.textContent = rangeText;

                    if (breakdownIndex > 0) {
                        const prevTotal = totalValues[breakdownIndex - 1];
                        const monthlyDelta = selectedTotal - prevTotal;
                        updateDeltaTone(monthlyDeltaNode, monthlyDelta);
                        if (monthlyDeltaNode) monthlyDeltaNode.textContent = formatSignedCurrency(monthlyDelta);
                        if (monthlyRateNode) {
                            if (prevTotal !== 0) {
                                const monthlyRate = (monthlyDelta / prevTotal) * 100;
                                monthlyRateNode.textContent = `${monthlyRate >= 0 ? '+' : ''}${monthlyRate.toFixed(1)}% vs previous point`;
                            } else {
                                monthlyRateNode.textContent = 'Previous point is 0';
                            }
                        }
                    } else {
                        updateDeltaTone(monthlyDeltaNode, 0);
                        if (monthlyDeltaNode) monthlyDeltaNode.textContent = '--';
                        if (monthlyRateNode) monthlyRateNode.textContent = 'No prior record';
                    }

                    const startTotal = totalValues[0] || 0;
                    const periodDelta = selectedTotal - startTotal;
                    updateDeltaTone(periodDeltaNode, periodDelta);
                    if (periodDeltaNode) periodDeltaNode.textContent = formatSignedCurrency(periodDelta);
                    if (periodRateNode) {
                        if (startTotal !== 0) {
                            const periodRate = (periodDelta / startTotal) * 100;
                            periodRateNode.textContent = `${periodRate >= 0 ? '+' : ''}${periodRate.toFixed(1)}% since ${labels[0]}`;
                        } else {
                            periodRateNode.textContent = `Since ${labels[0] || 'start'}`;
                        }
                    }

                    if (selectedTotal > 0) {
                        const dominantAsset = breakdownEntry.savings >= breakdownEntry.investments ? 'Cash' : 'Investments';
                        const dominantShare = Math.max(cashPctValue, invPctValue);
                        if (dominantAssetNode) dominantAssetNode.textContent = dominantAsset;
                        if (dominantShareNode) dominantShareNode.textContent = `${dominantShare.toFixed(1)}% of current allocation`;
                    } else {
                        if (dominantAssetNode) dominantAssetNode.textContent = '--';
                        if (dominantShareNode) dominantShareNode.textContent = 'No data available';
                    }

                    netWorthChart.data.labels = labels;
                    netWorthChart.data.datasets[0].data = savingsValues;
                    netWorthChart.data.datasets[1].data = investmentValues;
                    netWorthChart.update('none');

                    updateRangeFill(startIndex, endIndex);
                };

                if (rangeStartInput && rangeEndInput) {
                    rangeStartInput.min = '0';
                    rangeEndInput.min = '0';
                    rangeStartInput.max = String(maxIndex);
                    rangeEndInput.max = String(maxIndex);
                    rangeStartInput.value = '0';
                    rangeEndInput.value = String(maxIndex);

                    if (maxIndex <= 0) {
                        rangeStartInput.disabled = true;
                        rangeEndInput.disabled = true;
                        if (rangeSliderBlock) {
                            rangeSliderBlock.classList.add('is-disabled');
                        }
                    }

                    rangeStartInput.addEventListener('input', () => {
                        let start = Number(rangeStartInput.value);
                        const end = Number(rangeEndInput.value);
                        if (end - start < minGap) {
                            start = end - minGap;
                        }
                        start = Math.max(0, start);
                        rangeStartInput.value = String(start);
                        renderWindow(start, end);
                    });

                    rangeEndInput.addEventListener('input', () => {
                        const start = Number(rangeStartInput.value);
                        let end = Number(rangeEndInput.value);
                        if (end - start < minGap) {
                            end = start + minGap;
                        }
                        end = Math.min(maxIndex, end);
                        rangeEndInput.value = String(end);
                        renderWindow(start, end);
                    });
                }

                renderWindow(0, maxIndex);
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

        if (targetValue !== null) {
            const parsedValue = Number.parseFloat(targetValue);
            if (!Number.isFinite(parsedValue)) {
                return;
            }

            const boundedValue = Math.max(0, Math.min(parsedValue, 100));
            bar.setAttribute('aria-valuemin', '0');
            bar.setAttribute('aria-valuemax', '100');
            bar.setAttribute('aria-valuenow', boundedValue.toFixed(0));

            // Mantenemos el timeout para que se vea la animación al cargar
            setTimeout(() => {
                bar.style.width = boundedValue + '%';
            }, 150);
        }
    });

    // --- 3. BOOTSTRAP TOOLTIPS ---
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});
