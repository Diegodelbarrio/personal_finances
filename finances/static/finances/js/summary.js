/**
 * Finances Summary Module
 */
const SummaryModule = {
    _initialized: false,

    tableState: {
        rows: [],
        filteredRows: [],
        currentPage: 1,
        rowsPerPage: 10,
        sortState: { column: null, ascending: true }
    },

    init: function() {
        this.setupCharts();
        this.initTransactionTable();
    },

    setupCharts: function() {
        const expLabels = this.getData("labels-data");
        const expValues = this.getData("values-data");
        const savLabels = this.getData("savings-labels");
        const savValues = this.getData("savings-data");

        if (expLabels && expValues) {
            ChartFactory.createInteractiveDonut("expenseChart", "expenseLegendContainer", expLabels, expValues);
        }

        if (savLabels && savValues) {
            ChartFactory.createInteractiveDonut(
                "savingsRuleChart",
                "savingsLegendContainer",
                savLabels,
                savValues,
                ["#3b82f6", "#f59e0b", "#10b981"]
            );
        }
    },

    initTransactionTable: function() {
        const tableBody = document.getElementById("tableBody");
        if (!tableBody) return;

        this.tableState.rows = Array.from(document.querySelectorAll(".tx-row"));
        this.tableState.filteredRows = [...this.tableState.rows];
        this.updateVisibleCounter(this.tableState.filteredRows.length);

        const checkboxContainer = document.getElementById("checkboxContainer");
        const toggleBtn = document.getElementById("selectAllCats");
        const searchInput = document.getElementById("tableSearch");

        document.querySelectorAll(".sortable-header").forEach(header => {
            header.onclick = () => this.sortTable(header.getAttribute("data-sort"));
        });

        if (checkboxContainer) {
            checkboxContainer.innerHTML = "";
            this.buildCategoryFilters(checkboxContainer);
        }

        if (toggleBtn) {
            toggleBtn.onclick = () => {
                const checkboxes = checkboxContainer
                    ? checkboxContainer.querySelectorAll('input[type="checkbox"]')
                    : [];
                if (!checkboxes.length) return;

                const allChecked = [...checkboxes].every(cb => cb.checked);
                checkboxes.forEach(cb => {
                    cb.checked = !allChecked;
                });
                this.applyFilters();
            };
        }

        if (searchInput) {
            searchInput.oninput = () => this.applyFilters();
        }

        this.applyFilters();
    },

    buildCategoryFilters: function(container) {
        const categories = [...new Set(this.tableState.rows.map(row => row.dataset.cat.trim()))].sort();

        if (!categories.length) {
            const empty = document.createElement("p");
            empty.className = "text-muted small mb-0";
            empty.textContent = "No categories available for this period.";
            container.appendChild(empty);
            this.updateFilterUi(0, 0);
            return;
        }

        categories.forEach((category, index) => {
            const wrapper = document.createElement("div");
            wrapper.className = "form-check";

            const checkbox = document.createElement("input");
            checkbox.className = "form-check-input";
            checkbox.type = "checkbox";
            checkbox.value = category;
            checkbox.checked = true;
            checkbox.id = `cat-${this.slugify(category)}-${index}`;
            checkbox.addEventListener("change", () => this.applyFilters());

            const label = document.createElement("label");
            label.className = "form-check-label small ms-2";
            label.setAttribute("for", checkbox.id);
            label.textContent = category;

            wrapper.appendChild(checkbox);
            wrapper.appendChild(label);
            container.appendChild(wrapper);
        });

        this.updateFilterUi(categories.length, categories.length);
    },

    sortTable: function(column) {
        const state = this.tableState;

        if (state.sortState.column === column) {
            state.sortState.ascending = !state.sortState.ascending;
        } else {
            state.sortState.column = column;
            state.sortState.ascending = true;
        }

        this.sortFilteredRows();
        this.updateSortIcons(column);
        state.currentPage = 1;
        this.updateTable();
    },

    sortFilteredRows: function() {
        const state = this.tableState;
        const column = state.sortState.column;
        if (!column) return;

        state.filteredRows.sort((a, b) => {
            if (column === "category") {
                const valA = a.dataset.cat.toLowerCase();
                const valB = b.dataset.cat.toLowerCase();
                if (window.FinOrbitTables && typeof window.FinOrbitTables.compareValues === "function") {
                    return window.FinOrbitTables.compareValues(valA, valB, state.sortState.ascending);
                }
                return state.sortState.ascending ? valA.localeCompare(valB) : valB.localeCompare(valA);
            }

            const valA = this.getComparableValue(a, column);
            const valB = this.getComparableValue(b, column);
            if (window.FinOrbitTables && typeof window.FinOrbitTables.compareValues === "function") {
                return window.FinOrbitTables.compareValues(valA, valB, state.sortState.ascending);
            }
            return state.sortState.ascending ? valA - valB : valB - valA;
        });
    },

    getComparableValue: function(row, column) {
        if (column === "date") {
            return new Date(row.querySelector(".tx-date").dataset.val).getTime();
        }
        if (column === "amount") {
            return parseFloat(row.querySelector(".tx-amount").dataset.val);
        }
        return 0;
    },

    updateTable: function() {
        const state = this.tableState;
        const tableBody = document.getElementById("tableBody");
        const paginationInfo = document.getElementById("paginationInfo");

        if (!tableBody) return;

        const total = state.filteredRows.length;
        const pages = total > 0 ? Math.ceil(total / state.rowsPerPage) : 0;

        if (pages > 0 && state.currentPage > pages) {
            state.currentPage = pages;
        }

        this.updateVisibleCounter(total);

        if (total === 0) {
            const emptyMessage = this.getEmptyStateMessage();
            this.showEmptyState(emptyMessage);
            if (paginationInfo) paginationInfo.innerText = "No transactions to show";
            this.renderPagination(0);
            this.updateTotalSum();
            return;
        }

        const start = (state.currentPage - 1) * state.rowsPerPage;
        const end = start + state.rowsPerPage;
        const pageRows = state.filteredRows.slice(start, end);

        tableBody.innerHTML = "";
        pageRows.forEach(row => {
            row.style.display = "";
            tableBody.appendChild(row);
        });

        if (paginationInfo) {
            paginationInfo.innerText = `Showing ${start + 1} to ${Math.min(end, total)} of ${total} transactions`;
        }

        this.renderPagination(pages);
        this.updateTotalSum();
    },

    showEmptyState: function(message) {
        const tableBody = document.getElementById("tableBody");
        if (!tableBody) return;

        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state-cell text-center py-5">
                    <div class="empty-state-wrap">
                        <i class="bi bi-search fs-3 d-block mb-2 text-muted"></i>
                        <p class="mb-1 fw-semibold">${message}</p>
                        <small class="text-muted">Try another search or broaden your selected categories.</small>
                    </div>
                </td>
            </tr>`;
    },

    getEmptyStateMessage: function() {
        const searchInput = document.getElementById("tableSearch");
        const searchTerm = searchInput ? searchInput.value.trim() : "";
        const checkboxes = [...document.querySelectorAll('#checkboxContainer input[type="checkbox"]')];
        const activeCount = checkboxes.filter(cb => cb.checked).length;

        if (searchTerm) return "No transaction matches your search.";
        if (checkboxes.length > 0 && activeCount === 0) return "Select at least one category to display data.";
        if (checkboxes.length > 0 && activeCount < checkboxes.length) return "No results for the selected categories.";
        return "No transactions found for this period.";
    },

    renderPagination: function(pages) {
        const container = document.getElementById("paginationControls");
        if (!container) return;

        container.innerHTML = "";
        if (pages <= 1) return;

        const currentPage = this.tableState.currentPage;
        const paginationItems = window.FinOrbitTables && typeof window.FinOrbitTables.getPageWindow === "function"
            ? window.FinOrbitTables.getPageWindow(pages, currentPage)
            : this.getPaginationItems(pages, currentPage);

        this.createPaginationItem({
            container,
            label: '<i class="bi bi-chevron-left"></i>',
            page: currentPage - 1,
            disabled: currentPage === 1
        });

        paginationItems.forEach(item => {
            if (item === "...") {
                this.createPaginationItem({
                    container,
                    label: "...",
                    disabled: true,
                    isEllipsis: true
                });
            } else {
                this.createPaginationItem({
                    container,
                    label: item.toString(),
                    page: item,
                    active: item === currentPage
                });
            }
        });

        this.createPaginationItem({
            container,
            label: '<i class="bi bi-chevron-right"></i>',
            page: currentPage + 1,
            disabled: currentPage === pages
        });
    },

    createPaginationItem: function({ container, label, page = null, active = false, disabled = false, isEllipsis = false }) {
        const li = document.createElement("li");
        li.className = `page-item ${active ? "active" : ""} ${disabled ? "disabled" : ""}`.trim();

        const link = document.createElement("a");
        link.className = "page-link";
        link.href = "#";
        link.innerHTML = label;

        if (isEllipsis || disabled) {
            link.setAttribute("tabindex", "-1");
            link.setAttribute("aria-disabled", "true");
        } else {
            link.addEventListener("click", event => {
                event.preventDefault();
                this.tableState.currentPage = page;
                this.updateTable();
            });
        }

        li.appendChild(link);
        container.appendChild(li);
    },

    getPaginationItems: function(totalPages, currentPage) {
        if (totalPages <= 7) {
            return Array.from({ length: totalPages }, (_, i) => i + 1);
        }

        const items = [1];
        const start = Math.max(2, currentPage - 1);
        const end = Math.min(totalPages - 1, currentPage + 1);

        if (start > 2) items.push("...");
        for (let i = start; i <= end; i++) {
            items.push(i);
        }
        if (end < totalPages - 1) items.push("...");

        items.push(totalPages);
        return items;
    },

    updateTotalSum: function() {
        const totalDisplay = document.getElementById("tableTotalAmount");
        if (!totalDisplay) return;

        const sum = this.tableState.filteredRows.reduce((acc, row) => {
            return acc + parseFloat(row.querySelector(".tx-amount").dataset.val);
        }, 0);

        totalDisplay.innerText = FinancialFormatter.currency(sum);
        totalDisplay.className = sum < 0
            ? "h6 fw-bold text-danger mb-0"
            : "h6 fw-bold text-success mb-0";
    },

    updateSortIcons: function(activeColumn) {
        if (window.FinOrbitTables && typeof window.FinOrbitTables.updateSortHeaders === "function") {
            window.FinOrbitTables.updateSortHeaders({
                container: document.querySelector(".summary-shell") || document,
                activeColumn,
                ascending: this.tableState.sortState.ascending,
                defaultIconClass: "bi bi-arrow-down-up ms-1 small opacity-50",
                ascIconClass: "bi bi-sort-up ms-1",
                descIconClass: "bi bi-sort-down ms-1",
            });
            return;
        }

        document.querySelectorAll(".sortable-header").forEach(header => {
            header.setAttribute("aria-sort", "none");
            const icon = header.querySelector("i");
            if (icon) icon.className = "bi bi-arrow-down-up ms-1 small opacity-50";
        });

        const activeHeader = document.querySelector(`.sortable-header[data-sort="${activeColumn}"]`);
        if (!activeHeader) return;

        activeHeader.setAttribute(
            "aria-sort",
            this.tableState.sortState.ascending ? "ascending" : "descending"
        );

        const icon = activeHeader.querySelector("i");
        if (icon) {
            icon.className = this.tableState.sortState.ascending
                ? "bi bi-sort-up ms-1"
                : "bi bi-sort-down ms-1";
        }
    },

    applyFilters: function() {
        const state = this.tableState;
        const searchInput = document.getElementById("tableSearch");
        const searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : "";

        const checkboxes = [...document.querySelectorAll('#checkboxContainer input[type="checkbox"]')];
        const activeCats = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
        const hasCategoryFilters = checkboxes.length > 0;

        state.filteredRows = state.rows.filter(row => {
            const matchesCategory = !hasCategoryFilters || activeCats.includes(row.dataset.cat.trim());
            const matchesSearch = row.innerText.toLowerCase().includes(searchTerm);
            return matchesCategory && matchesSearch;
        });

        if (state.sortState.column) {
            this.sortFilteredRows();
        }

        this.updateFilterUi(checkboxes.length, activeCats.length);
        state.currentPage = 1;
        this.updateTable();
    },

    updateFilterUi: function(totalCategories, activeCategories) {
        const badge = document.getElementById("activeFiltersCount");
        if (badge) {
            const showBadge = totalCategories > 0 && activeCategories !== totalCategories;
            badge.classList.toggle("d-none", !showBadge);
            if (showBadge) {
                badge.textContent = `${activeCategories}/${totalCategories}`;
            }
        }

        this.updateToggleButtonLabel(totalCategories, activeCategories);
    },

    updateToggleButtonLabel: function(totalCategories, activeCategories) {
        const toggleBtn = document.getElementById("selectAllCats");
        if (!toggleBtn) return;

        if (totalCategories === 0) {
            toggleBtn.textContent = "No Categories";
            toggleBtn.disabled = true;
            return;
        }

        toggleBtn.disabled = false;
        toggleBtn.textContent = activeCategories === totalCategories ? "Clear All" : "Select All";
    },

    slugify: function(value) {
        const normalized = String(value)
            .toLowerCase()
            .trim()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");

        return normalized || "category";
    },

    updateVisibleCounter: function(count) {
        const visibleRowsCounter = document.getElementById("visibleRowsCounter");
        if (!visibleRowsCounter) return;
        visibleRowsCounter.innerText = `${count} visible`;
    },

    getData: function(id) {
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : null;
    },

    safeInit: function() {
        if (this._initialized) return;
        this._initialized = true;
        this.init();
    }
};

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => SummaryModule.safeInit());
} else {
    SummaryModule.safeInit();
}

if (window.jQuery) {
    $(document).ready(function() {
        SummaryModule.safeInit();
    });
}
