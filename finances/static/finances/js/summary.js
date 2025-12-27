/**
 * Finances Summary Module
 */
const SummaryModule = {
    // Variables de estado de la tabla
    tableState: {
        rows: [],
        filteredRows: [],
        currentPage: 1,
        rowsPerPage: 10,
        sortState: { column: null, ascending: true }
    },

    init: function() {
        // 1. Inicializar Gráficos
        this.setupCharts();

        // 2. Inicializar la tabla
        this.initTransactionTable();
    },

    setupCharts: function() {
        const expLabels = this.getData('labels-data');
        const expValues = this.getData('values-data');
        const savLabels = this.getData('savings-labels');
        const savValues = this.getData('savings-data');

        if (expLabels && expValues) {
            ChartFactory.createInteractiveDonut('expenseChart', 'expenseLegendContainer', expLabels, expValues);
        }

        if (savLabels && savValues) {
            ChartFactory.createInteractiveDonut(
                'savingsRuleChart', 
                'savingsLegendContainer', 
                savLabels, 
                savValues, 
                ['#10b981', '#6366f1', '#f59e0b']
            );
        }
    },

    initTransactionTable: function() {
        const tableBody = document.getElementById('tableBody');
        if (!tableBody) return;

        // Configuración inicial del estado
        this.tableState.rows = Array.from(document.querySelectorAll('.tx-row'));
        this.tableState.filteredRows = [...this.tableState.rows];

        // Referencias a elementos del DOM
        const checkboxContainer = document.getElementById('checkboxContainer');
        const toggleBtn = document.getElementById('selectAllCats');
        const searchInput = document.getElementById('tableSearch');

        // --- EVENTOS DE ORDENACIÓN ---
        document.querySelectorAll('.sortable-header').forEach(header => {
            header.onclick = () => this.sortTable(header.getAttribute('data-sort'));
        });

        // --- GENERAR FILTROS DE CATEGORÍA ---
        const cats = [...new Set(this.tableState.rows.map(r => r.dataset.cat.trim()))].sort();
        cats.forEach(c => {
            const div = document.createElement('div');
            div.className = 'form-check mb-2';
            div.innerHTML = `
                <input class="form-check-input" type="checkbox" value="${c}" checked id="cat-${c}">
                <label class="form-check-label small ms-2" for="cat-${c}">${c}</label>`;
            div.querySelector('input').onchange = () => this.applyFilters();
            checkboxContainer.appendChild(div);
        });

        if (toggleBtn) {
            toggleBtn.onclick = () => {
                const cbs = checkboxContainer.querySelectorAll('input');
                const anyUnchecked = [...cbs].some(c => !c.checked);
                cbs.forEach(c => c.checked = anyUnchecked);
                this.applyFilters();
            };
        }

        // --- BUSCADOR ---
        if (searchInput) {
            searchInput.oninput = () => this.applyFilters();
        }

        this.updateTable();
    },

    sortTable: function(column) {
        const state = this.tableState;
        if (state.sortState.column === column) {
            state.sortState.ascending = !state.sortState.ascending;
        } else {
            state.sortState.column = column;
            state.sortState.ascending = true;
        }

        state.filteredRows.sort((a, b) => {
            let valA, valB;
            if (column === 'date') {
                valA = new Date(a.querySelector('.tx-date').dataset.val).getTime();
                valB = new Date(b.querySelector('.tx-date').dataset.val).getTime();
            } else if (column === 'amount') {
                valA = parseFloat(a.querySelector('.tx-amount').dataset.val);
                valB = parseFloat(b.querySelector('.tx-amount').dataset.val);
            } else {
                valA = a.dataset.cat.toLowerCase();
                valB = b.dataset.cat.toLowerCase();
                return state.sortState.ascending ? valA.localeCompare(valB) : valB.localeCompare(valA);
            }
            return state.sortState.ascending ? valA - valB : valB - valA;
        });

        this.updateSortIcons(column);
        state.currentPage = 1;
        this.updateTable();
    },

    updateTable: function() {
        const state = this.tableState;
        const tableBody = document.getElementById('tableBody');
        const total = state.filteredRows.length;
        const pages = Math.ceil(total / state.rowsPerPage);
        
        const start = (state.currentPage - 1) * state.rowsPerPage;
        const end = start + state.rowsPerPage;
        const pageRows = state.filteredRows.slice(start, end);

        tableBody.innerHTML = ''; 
        pageRows.forEach(r => {
            r.style.display = ''; 
            tableBody.appendChild(r);
        });
        
        document.getElementById('paginationInfo').innerText = 
            `Showing ${total > 0 ? start + 1 : 0} to ${Math.min(end, total)} of ${total}`;
        
        this.renderPagination(pages);
        this.updateTotalSum();
    },

    renderPagination: function(pages) {
        const container = document.getElementById('paginationControls');
        container.innerHTML = '';
        if (pages <= 1) return;

        for (let i = 1; i <= pages; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === this.tableState.currentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            li.onclick = (e) => { 
                e.preventDefault(); 
                this.tableState.currentPage = i; 
                this.updateTable(); 
            };
            container.appendChild(li);
        }
    },

    updateTotalSum: function() {
        const totalDisplay = document.getElementById('tableTotalAmount');
        let sum = this.tableState.filteredRows.reduce((acc, r) => 
            acc + parseFloat(r.querySelector('.tx-amount').dataset.val), 0
        );
        
        // Uso del formateador global
        totalDisplay.innerText = FinancialFormatter.currency(sum);
        totalDisplay.className = sum < 0 ? 'h6 fw-bold text-danger mb-0' : 'h6 fw-bold text-success mb-0';
    },

    updateSortIcons: function(activeColumn) {
        document.querySelectorAll('.sortable-header i').forEach(icon => {
            icon.className = 'bi bi-arrow-down-up ms-1 small opacity-50';
        });
        const activeHeader = document.querySelector(`.sortable-header[data-sort="${activeColumn}"] i`);
        if (activeHeader) {
            activeHeader.className = this.tableState.sortState.ascending ? 'bi bi-sort-up ms-1' : 'bi bi-sort-down ms-1';
            activeHeader.classList.remove('opacity-50');
        }
    },

    applyFilters: function() {
        const state = this.tableState;
        const searchInput = document.getElementById('tableSearch');
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const activeCats = [...document.querySelectorAll('#checkboxContainer input:checked')].map(cb => cb.value);

        state.filteredRows = state.rows.filter(r => {
            const matchesCat = activeCats.includes(r.dataset.cat.trim());
            const matchesSearch = r.innerText.toLowerCase().includes(searchTerm);
            return matchesCat && matchesSearch;
        });
        
        state.currentPage = 1;
        this.updateTable();
    },

    getData: function(id) {
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : null;
    }
};

// Inicialización
$(document).ready(function() {
    SummaryModule.init();
});