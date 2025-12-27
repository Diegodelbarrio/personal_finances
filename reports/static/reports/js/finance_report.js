const SummaryModule = {
    init: function() {
        this.setupCharts();
    },

    // Función auxiliar para leer los JSON del HTML
    getData: function(id) {
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : null;
    },

    setupCharts: function() {
        const savLabels = this.getData('savings-labels');
        const savValues = this.getData('savings-data');

        if (savLabels && savValues) {
            ChartFactory.createInteractiveDonut(
                'AnnualsavingsRuleChart', 
                'AnnualsavingsLegendContainer', 
                savLabels, 
                savValues, 
                ['#10b981', '#6366f1', '#f59e0b']
            );
        }
    }
};

// Inicialización
$(document).ready(function() {
    SummaryModule.init();
});