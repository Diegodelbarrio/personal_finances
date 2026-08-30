document.addEventListener('DOMContentLoaded', function () {
    const ctx = document.getElementById('compoundInterestChart').getContext('2d');

    // Financial Constants
    const monthlyContribution = 200;
    const annualRate = 0.07;
    const years = 30;
    const labels = [];
    const savingsData = [];  // Escenario: Solo ahorro (0%)
    const investedData = []; // Escenario: Inversión (7%)

    let totalPrincipal = 0;
    let totalBalance = 0;
    const locale = document.documentElement.lang || 'en-GB';
    const currency = document.documentElement.dataset.currency || 'EUR';

    // Calculation Logic (Monthly Compounding)
    for (let year = 0; year <= years; year++) {
        labels.push('Year ' + year);
        
        if (year > 0) {
            for (let month = 1; month <= 12; month++) {
                totalBalance = (totalBalance + monthlyContribution) * (1 + annualRate / 12);
                totalPrincipal += monthlyContribution;
            }
        }
        
        savingsData.push(totalPrincipal);
        investedData.push(totalBalance);
    }

    // Chart Configuration
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Investment (7% per annum)',
                    data: investedData,
                    borderColor: '#198754',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4
                },
                {
                    label: 'Savings only (0%)',
                    data: savingsData,
                    borderColor: '#0d6efd',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false 
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': ' + 
                                   new Intl.NumberFormat(locale, { style: 'currency', currency }).format(context.raw);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return new Intl.NumberFormat(locale, {
                                style: 'currency',
                                currency,
                                notation: 'compact',
                                maximumFractionDigits: 1
                            }).format(value);
                        }
                    },
                    grid: {
                        display: false
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
});
