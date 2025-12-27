const HoldingsModule = {
    init: function() {
        // Buscamos los elementos para asegurar que existen antes de parsear
        const labelsEl = document.getElementById('bar-labels');
        const dataEl = document.getElementById('bar-datasets');

        if (labelsEl && dataEl) {
            const labels = JSON.parse(labelsEl.textContent);
            const datasets = JSON.parse(dataEl.textContent);
            
            ChartFactory.createStackedBarChart('holdingsEvolutionChart', labels, datasets);
        }
    }
};

// ESTO ES LO QUE TE FALTA:
$(document).ready(function() {
    HoldingsModule.init();
});