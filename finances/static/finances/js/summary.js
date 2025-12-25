/**
 * Crea un gráfico de Donut con leyenda interactiva lateral.
 * @param {string} canvasId - ID del elemento canvas
 * @param {string} legendId - ID del contenedor div para la leyenda
 * @param {Array} labels - Array de etiquetas
 * @param {Array} values - Array de valores numéricos
 * @param {Array} colors - Array de colores hexadecimales
 */
function createInteractiveDonut(canvasId, legendId, labels, values, colors) {
    const ctx = document.getElementById(canvasId);
    const legendContainer = document.getElementById(legendId);
    
    if (!ctx || !legendContainer || !values || values.length === 0) return;

    // 1. Preparar datos (Ordenar de mayor a menor para consistencia visual)
    let chartData = labels.map((label, i) => ({
        label: label,
        value: values[i],
        color: colors[i % colors.length]
    })).sort((a, b) => b.value - a.value);

    const sortedLabels = chartData.map(d => d.label);
    const sortedValues = chartData.map(d => d.value);
    const sortedColors = chartData.map(d => d.color);
    const total = sortedValues.reduce((a, b) => a + b, 0);

    // 2. Crear Gráfico Chart.js
    const chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: sortedLabels,
            datasets: [{
                data: sortedValues,
                backgroundColor: sortedColors,
                cutout: '50%',
                borderColor: '#fff',
                borderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, // Ocultar leyenda nativa
            tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            let value = context.raw || 0;
                            // Formatea el número y añade el símbolo €
                            return ` ${value.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €`;
                        }
                    }
                },
            },
            onHover: (event, chartElement) => {
                // Resetear estilos de todos los items de leyenda
                const legendItems = legendContainer.querySelectorAll('.legend-card');
                legendItems.forEach(el => { 
                    el.style.backgroundColor = ''; 
                    el.style.transform = ''; 
                });
                
                // Si el ratón está sobre un segmento del gráfico, resaltar la leyenda correspondiente
                if (chartElement.length > 0) {
                    const index = chartElement[0].index;
                    const targetCard = legendItems[index];
                    if (targetCard) {
                        targetCard.style.backgroundColor = '#f1f5f9';
                        targetCard.style.transform = 'translateX(4px)';
                    }
                }
            }
        }
    });

    // 3. Generar HTML de la Leyenda Personalizada
    legendContainer.innerHTML = '';
    chartData.forEach((item, i) => {
        const percentage = total > 0 ? ((item.value / total) * 100).toFixed(1) : 0;
        
        // Crear tarjeta
        const card = document.createElement('div');
        card.className = 'legend-card'; // Clase CSS reutilizable
        card.innerHTML = `
            <div style="width:8px; height:8px; border-radius:50%; background:${item.color}; flex-shrink:0;"></div>
            <div class="ms-2 flex-grow-1 d-flex justify-content-between align-items-center">
                <div>
                    <div class="fw-bold" style="font-size:0.8rem;">${item.label}</div>
                    <div class="text-muted" style="font-size:0.65rem;">${item.value.toLocaleString('de-DE', { minimumFractionDigits: 2 })} €</div>
                </div>
                <div class="fw-bold" style="font-size:0.85rem;">${percentage}%</div>
            </div>`;

        // Eventos de ratón para interactuar con el gráfico
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
}

/**
 * Inicializa la lógica de la tabla de transacciones (Filtros y Paginación)
 */
/**
 * Inicializa la lógica de la tabla de transacciones (Filtros, Paginación y Sorting)
 */
function initTransactionTable() {
    const tableBody = document.getElementById('tableBody');
    if (!tableBody) return;

    // Guardamos las filas originales
    const rows = Array.from(document.querySelectorAll('.tx-row'));
    const checkboxContainer = document.getElementById('checkboxContainer');
    const totalDisplay = document.getElementById('tableTotalAmount');
    const paginationControls = document.getElementById('paginationControls');
    const paginationInfo = document.getElementById('paginationInfo');
    
    let currentPage = 1;
    const rowsPerPage = 10;
    let filteredRows = [...rows];
    let sortState = { column: null, ascending: true };

    // --- LÓGICA DE ORDENACIÓN ---
    function sortTable(column) {
        if (sortState.column === column) {
            sortState.ascending = !sortState.ascending;
        } else {
            sortState.column = column;
            sortState.ascending = true;
        }

        filteredRows.sort((a, b) => {
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
                return sortState.ascending ? valA.localeCompare(valB) : valB.localeCompare(valA);
            }

            return sortState.ascending ? valA - valB : valB - valA;
        });

        updateSortIcons(column);
        currentPage = 1;
        updateTable();
    }

    // --- ACTUALIZACIÓN DE LA VISTA (CORREGIDO) ---
    function updateTable() {
        const total = filteredRows.length;
        const pages = Math.ceil(total / rowsPerPage);
        
        // 1. Ocultar todas las filas primero
        rows.forEach(r => r.style.display = 'none');

        // 2. Obtener las filas de la página actual
        const start = (currentPage - 1) * rowsPerPage;
        const end = start + rowsPerPage;
        const pageRows = filteredRows.slice(start, end);

        // 3. LIMPIAR Y RE-INSERTAR (Esto es lo que garantiza el orden visual)
        tableBody.innerHTML = ''; 
        pageRows.forEach(r => {
            r.style.display = ''; // Asegurarse de que sea visible
            tableBody.appendChild(r); // Re-insertar en el nuevo orden
        });
        
        // Actualizar información de paginación
        paginationInfo.innerText = `Showing ${total > 0 ? start + 1 : 0} to ${Math.min(end, total)} of ${total}`;
        
        // Renderizar controles de paginación
        renderPagination(pages);
        
        // Calcular Total Visible
        updateTotalSum();
    }

    function renderPagination(pages) {
        paginationControls.innerHTML = '';
        if (pages <= 1) return;

        for (let i = 1; i <= pages; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === currentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            li.onclick = (e) => { 
                e.preventDefault(); 
                currentPage = i; 
                updateTable(); 
            };
            paginationControls.appendChild(li);
        }
    }

    function updateTotalSum() {
        let sum = filteredRows.reduce((acc, r) => acc + parseFloat(r.querySelector('.tx-amount').dataset.val), 0);
        totalDisplay.innerText = sum.toLocaleString('de-DE', { minimumFractionDigits: 2 }) + ' €';
        totalDisplay.className = sum < 0 ? 'h6 fw-bold text-danger mb-0' : 'h6 fw-bold text-success mb-0';
    }

    function updateSortIcons(activeColumn) {
        document.querySelectorAll('.sortable-header i').forEach(icon => {
            icon.className = 'bi bi-arrow-down-up ms-1 small opacity-50';
        });
        const activeHeader = document.querySelector(`.sortable-header[data-sort="${activeColumn}"] i`);
        if (activeHeader) {
            activeHeader.className = sortState.ascending ? 'bi bi-sort-up ms-1' : 'bi bi-sort-down ms-1';
            activeHeader.classList.remove('opacity-50');
        }
    }

    // --- FILTROS ---
    function applyFilters() {
        const active = [...checkboxContainer.querySelectorAll('input:checked')].map(cb => cb.value);
        filteredRows = rows.filter(r => active.includes(r.dataset.cat.trim()));
        
        if (sortState.column) {
            const currentColumn = sortState.column;
            sortState.column = null; // Reset para forzar la misma dirección
            sortTable(currentColumn);
        } else {
            currentPage = 1;
            updateTable();
        }
    }

    // --- INICIALIZACIÓN DE EVENTOS ---
    document.querySelectorAll('.sortable-header').forEach(header => {
        header.onclick = function() {
            sortTable(this.getAttribute('data-sort'));
        };
    });

    // Generar checkboxes de categorías
    const cats = [...new Set(rows.map(r => r.dataset.cat.trim()))].sort();
    cats.forEach(c => {
        const div = document.createElement('div');
        div.className = 'form-check mb-2';
        div.innerHTML = `<input class="form-check-input" type="checkbox" value="${c}" checked><label class="form-check-label small ms-2">${c}</label>`;
        div.querySelector('input').onchange = applyFilters;
        checkboxContainer.appendChild(div);
    });

    const toggleBtn = document.getElementById('selectAllCats');
    if(toggleBtn) {
        toggleBtn.onclick = () => {
            const cbs = checkboxContainer.querySelectorAll('input');
            const all = [...cbs].every(c => c.checked);
            cbs.forEach(c => c.checked = !all);
            applyFilters();
        };
    }

    // Carga inicial
    updateTable();
}