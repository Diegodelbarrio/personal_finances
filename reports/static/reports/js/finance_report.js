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
        // Gráfica de Distribución de Gastos Anuales
        const expLabels = this.getData('annual-category-labels');
        const expData = this.getData('annual-category-data');

        if (expLabels && expData && expLabels.length > 0) {
            ChartFactory.createInteractiveDonut('annualExpenseChart', 'annualExpenseLegendContainer', expLabels, expData);
        }

        const savLabels = this.getData('savings-labels');
        const savValues = this.getData('savings-data');

        if (savLabels && savValues) {
            ChartFactory.createInteractiveDonut(
                'AnnualsavingsRuleChart', 
                'AnnualsavingsLegendContainer', 
                savLabels, 
                savValues, 
                ['#3b82f6', '#f59e0b', '#10b981']
            );
        }
    }
};

// Inicialización
$(document).ready(function() {
    SummaryModule.init();
});
