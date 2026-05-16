const CategoryManagerModule = {
    categoryState: null,
    subcategoryState: null,

    init: function() {
        this.bindFormStateSync();
        this.initSubcategoryQuickAdd();
        this.initDefaultPresetSelector();
        this.initQuickActionsDropdowns();
        this.bindDeleteConfirmations();
        this.initCategoriesTable();
        this.initSubcategoriesTable();
    },

    initQuickActionsDropdowns: function() {
        if (window.FinOrbitTables && typeof window.FinOrbitTables.initActionDropdowns === "function") {
            window.FinOrbitTables.initActionDropdowns(document);
            return;
        }

        if (!window.bootstrap || !window.bootstrap.Dropdown) {
            return;
        }

        const upsertModifier = (modifiers, modifier) => {
            const index = modifiers.findIndex((item) => item && item.name === modifier.name);
            if (index >= 0) {
                modifiers[index] = modifier;
                return modifiers;
            }
            return [...modifiers, modifier];
        };

        document
            .querySelectorAll('.quick-actions-trigger[data-bs-toggle="dropdown"]')
            .forEach((trigger) => {
                bootstrap.Dropdown.getOrCreateInstance(trigger, {
                    popperConfig(defaultBsPopperConfig) {
                        const baseConfig = defaultBsPopperConfig || {};
                        let modifiers = Array.isArray(baseConfig.modifiers)
                            ? [...baseConfig.modifiers]
                            : [];

                        modifiers = upsertModifier(modifiers, {
                            name: "flip",
                            options: {
                                fallbackPlacements: [
                                    "top-end",
                                    "bottom-end",
                                    "top-start",
                                    "bottom-start",
                                ],
                            },
                        });

                        modifiers = upsertModifier(modifiers, {
                            name: "preventOverflow",
                            options: {
                                boundary: "viewport",
                                altAxis: true,
                                padding: 8,
                            },
                        });

                        return {
                            ...baseConfig,
                            strategy: "fixed",
                            placement: "bottom-end",
                            modifiers,
                        };
                    },
                });
            });
    },

    bindFormStateSync: function() {
        const transactionTypeField = document.getElementById("id_transaction_type");
        if (!transactionTypeField) {
            return;
        }

        transactionTypeField.addEventListener("change", () => this.syncCategoryFormState());
        this.syncCategoryFormState();
    },

    syncCategoryFormState: function() {
        const transactionTypeField = document.getElementById("id_transaction_type");
        const expenseTypeField = document.getElementById("id_expense_type");
        const housingField = document.getElementById("id_is_housing");

        if (!transactionTypeField || !expenseTypeField) {
            return;
        }

        const isIncome = transactionTypeField.value === "INCOME";
        if (isIncome) {
            expenseTypeField.value = "N/A";
            expenseTypeField.classList.add("bg-light");
            if (housingField) {
                housingField.checked = false;
                housingField.setAttribute("disabled", "disabled");
            }
            return;
        }

        expenseTypeField.classList.remove("bg-light");
        if (expenseTypeField.value === "N/A") {
            expenseTypeField.value = "VARIABLE";
        }
        if (housingField) {
            housingField.removeAttribute("disabled");
        }
    },

    initSubcategoryQuickAdd: function() {
        const textarea = document.getElementById("id_subcategory_names");
        if (!textarea) {
            return;
        }

        const quickInput = document.getElementById("quickSubcategoryName");
        const addButton = document.getElementById("addQuickSubcategory");
        const previewContainer = document.getElementById("subcategoryPreviewChips");

        const parseNames = (value) => {
            const seen = new Set();
            const names = [];
            String(value || "")
                .split(/[\n,;]+/g)
                .map((item) => item.trim())
                .filter(Boolean)
                .forEach((name) => {
                    const normalized = name.toLocaleLowerCase();
                    if (seen.has(normalized)) {
                        return;
                    }
                    seen.add(normalized);
                    names.push(name);
                });
            return names;
        };

        const renderPreview = () => {
            if (!previewContainer) {
                return;
            }

            const names = parseNames(textarea.value);
            previewContainer.innerHTML = "";
            names.forEach((name) => {
                const chip = document.createElement("span");
                chip.className = "subcategory-preview-chip";
                chip.textContent = name;
                previewContainer.appendChild(chip);
            });
        };

        const appendSubcategory = () => {
            if (!quickInput) {
                return;
            }

            const candidate = quickInput.value.trim();
            if (!candidate) {
                return;
            }

            const names = parseNames(textarea.value);
            const exists = names.some(
                (existingName) => existingName.toLocaleLowerCase() === candidate.toLocaleLowerCase()
            );
            if (!exists) {
                names.push(candidate);
                textarea.value = names.join("\n");
                renderPreview();
            }
            quickInput.value = "";
            quickInput.focus();
        };

        if (addButton) {
            addButton.addEventListener("click", appendSubcategory);
        }
        if (quickInput) {
            quickInput.addEventListener("keydown", (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    appendSubcategory();
                }
            });
        }

        textarea.addEventListener("input", renderPreview);
        renderPreview();
    },

    initDefaultPresetSelector: function() {
        const form = document.getElementById("defaultCategoriesForm");
        if (!form) {
            return;
        }

        const categoryToggles = Array.from(form.querySelectorAll(".preset-category-toggle"));
        const subcategoryChecks = Array.from(form.querySelectorAll('input[name="subcategory_keys"]'));

        const syncState = () => {
            categoryToggles.forEach((toggle) => {
                const categoryKey = toggle.dataset.categoryKey;
                if (!categoryKey) {
                    return;
                }

                const shouldEnable = toggle.checked;
                const group = form.querySelector(`[data-subcategory-group="${categoryKey}"]`);
                const subcategoryChecks = form.querySelectorAll(
                    `input[name="subcategory_keys"][data-category-key="${categoryKey}"]`
                );

                subcategoryChecks.forEach((checkbox) => {
                    checkbox.disabled = !shouldEnable;
                    if (!shouldEnable) {
                        checkbox.checked = false;
                    }
                });

                if (group) {
                    group.classList.toggle("is-disabled", !shouldEnable);
                }
            });
        };

        const findCategoryToggle = (categoryKey) => (
            categoryToggles.find((toggle) => toggle.dataset.categoryKey === categoryKey)
        );

        const isRecommended = (checkbox) => checkbox.dataset.defaultSelected === "true";

        const applyPresetAction = (action) => {
            categoryToggles.forEach((toggle) => {
                if (toggle.disabled) {
                    return;
                }
                if (action === "all") {
                    toggle.checked = true;
                    return;
                }
                if (action === "recommended") {
                    toggle.checked = isRecommended(toggle);
                    return;
                }
                if (action === "clear") {
                    toggle.checked = false;
                }
            });

            subcategoryChecks.forEach((checkbox) => {
                if (action === "all") {
                    checkbox.checked = true;
                    return;
                }
                if (action === "recommended") {
                    const categoryToggle = findCategoryToggle(checkbox.dataset.categoryKey);
                    checkbox.checked = Boolean(
                        categoryToggle
                        && categoryToggle.checked
                        && isRecommended(checkbox)
                    );
                    return;
                }
                if (action === "clear") {
                    checkbox.checked = false;
                }
            });

            syncState();
        };

        categoryToggles.forEach((toggle) => {
            toggle.addEventListener("change", syncState);
        });

        form.querySelectorAll("[data-preset-action]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                applyPresetAction(button.dataset.presetAction);
            });
        });

        syncState();
    },

    bindDeleteConfirmations: function() {
        document.addEventListener("submit", (event) => {
            const form = event.target;
            if (!(form instanceof HTMLFormElement)) {
                return;
            }

            if (form.matches(".js-delete-category-form")) {
                const categoryName = form.dataset.categoryName || "this category";
                if (!window.confirm(`Delete "${categoryName}"? This action cannot be undone.`)) {
                    event.preventDefault();
                }
                return;
            }

            if (form.matches(".js-delete-subcategory-form")) {
                const subcategoryName = form.dataset.subcategoryName || "this subcategory";
                if (!window.confirm(`Delete "${subcategoryName}"? This action cannot be undone.`)) {
                    event.preventDefault();
                }
            }
        });
    },

    initCategoriesTable: function() {
        const tableBody = document.getElementById("categoriesTableBody");
        if (!tableBody) {
            return;
        }

        this.categoryState = {
            tableKey: "categories",
            tableBody,
            rows: Array.from(tableBody.querySelectorAll(".category-row")),
            filteredRows: [],
            currentPage: 1,
            rowsPerPage: 10,
            sortState: { column: null, ascending: true },
            emptyColspan: 8,
            visibleCountId: "categoriesVisibleCount",
            noDataMessage: "No categories match current filters.",
            pagination: {
                wrapperId: "categoriesPaginationWrapper",
                infoId: "categoriesPaginationInfo",
                controlsId: "categoriesPaginationControls",
            },
            selection: {
                rowCheckboxSelector: ".category-row-select",
                selectAllId: "selectVisibleCategories",
                selectedCountId: "categorySelectedCount",
                batchFormId: "categoryBatchDeleteForm",
                batchIdsContainerId: "categoryBatchIds",
                batchInputName: "category_ids",
                deleteButtonId: "categoryBatchDeleteButton",
                itemLabel: "category",
            },
        };

        const nameFilter = document.getElementById("categoryNameFilter");
        const typeFilter = document.getElementById("categoryTypeFilter");
        const expenseFilter = document.getElementById("categoryExpenseFilter");
        const housingFilter = document.getElementById("categoryHousingFilter");
        const clearButton = document.getElementById("clearCategoryFilters");

        [nameFilter, typeFilter, expenseFilter, housingFilter].forEach((field) => {
            if (!field) {
                return;
            }
            const eventName = field.tagName === "SELECT" ? "change" : "input";
            field.addEventListener(eventName, () => {
                this.categoryState.currentPage = 1;
                this.applyCategoryFilters();
            });
        });

        if (clearButton) {
            clearButton.addEventListener("click", () => {
                if (nameFilter) nameFilter.value = "";
                if (typeFilter) typeFilter.value = "";
                if (expenseFilter) expenseFilter.value = "";
                if (housingFilter) housingFilter.value = "";
                this.categoryState.sortState = { column: null, ascending: true };
                this.categoryState.currentPage = 1;
                this.updateSortIcons("categories");
                this.applyCategoryFilters();
            });
        }

        document.querySelectorAll('.sortable-header[data-table="categories"]').forEach((header) => {
            header.addEventListener("click", () => {
                this.sortRows(this.categoryState, header.dataset.sort);
                this.applyCategoryFilters();
            });
        });

        this.initSelectionControls(this.categoryState);
        this.applyCategoryFilters();
    },

    initSubcategoriesTable: function() {
        const tableBody = document.getElementById("subcategoriesTableBody");
        if (!tableBody) {
            return;
        }

        this.subcategoryState = {
            tableKey: "subcategories",
            tableBody,
            rows: Array.from(tableBody.querySelectorAll(".subcategory-row")),
            filteredRows: [],
            currentPage: 1,
            rowsPerPage: 10,
            sortState: { column: null, ascending: true },
            emptyColspan: 8,
            visibleCountId: "subcategoriesVisibleCount",
            noDataMessage: "No subcategories match current filters.",
            pagination: {
                wrapperId: "subcategoriesPaginationWrapper",
                infoId: "subcategoriesPaginationInfo",
                controlsId: "subcategoriesPaginationControls",
            },
            selection: {
                rowCheckboxSelector: ".subcategory-row-select",
                selectAllId: "selectVisibleSubcategories",
                selectedCountId: "subcategorySelectedCount",
                batchFormId: "subcategoryBatchDeleteForm",
                batchIdsContainerId: "subcategoryBatchIds",
                batchInputName: "subcategory_ids",
                deleteButtonId: "subcategoryBatchDeleteButton",
                itemLabel: "subcategory",
            },
        };

        const nameFilter = document.getElementById("subcategoryNameFilter");
        const categoryFilter = document.getElementById("subcategoryCategoryFilter");
        const budgetGroupFilter = document.getElementById("subcategoryBudgetGroupFilter");
        const expenseNatureFilter = document.getElementById("subcategoryExpenseNatureFilter");
        const essentialFilter = document.getElementById("subcategoryEssentialFilter");
        const clearButton = document.getElementById("clearSubcategoryFilters");

        [nameFilter, categoryFilter, budgetGroupFilter, expenseNatureFilter, essentialFilter].forEach((field) => {
            if (!field) {
                return;
            }
            const eventName = field.tagName === "SELECT" ? "change" : "input";
            field.addEventListener(eventName, () => {
                this.subcategoryState.currentPage = 1;
                this.applySubcategoryFilters();
            });
        });

        if (clearButton) {
            clearButton.addEventListener("click", () => {
                if (nameFilter) nameFilter.value = "";
                if (categoryFilter) categoryFilter.value = "";
                if (budgetGroupFilter) budgetGroupFilter.value = "";
                if (expenseNatureFilter) expenseNatureFilter.value = "";
                if (essentialFilter) essentialFilter.value = "";
                this.subcategoryState.sortState = { column: null, ascending: true };
                this.subcategoryState.currentPage = 1;
                this.updateSortIcons("subcategories");
                this.applySubcategoryFilters();
            });
        }

        document.querySelectorAll('.sortable-header[data-table="subcategories"]').forEach((header) => {
            header.addEventListener("click", () => {
                this.sortRows(this.subcategoryState, header.dataset.sort);
                this.applySubcategoryFilters();
            });
        });

        this.initSelectionControls(this.subcategoryState);
        this.applySubcategoryFilters();
    },

    initSelectionControls: function(state) {
        const selection = state.selection;
        const selectAll = document.getElementById(selection.selectAllId);
        const form = document.getElementById(selection.batchFormId);
        const idsContainer = document.getElementById(selection.batchIdsContainerId);

        state.tableBody.addEventListener("change", (event) => {
            const checkbox = event.target;
            if (!checkbox.matches(selection.rowCheckboxSelector)) {
                return;
            }
            this.updateSelectionState(state);
        });

        if (selectAll) {
            selectAll.addEventListener("change", () => {
                this.getRenderedSelectionCheckboxes(state).forEach((checkbox) => {
                    checkbox.checked = selectAll.checked;
                });
                this.updateSelectionState(state);
            });
        }

        if (form && idsContainer) {
            form.addEventListener("submit", (event) => {
                const selectedIds = this.getSelectedRowIds(state);
                idsContainer.innerHTML = "";

                if (!selectedIds.length) {
                    event.preventDefault();
                    this.updateSelectionState(state);
                    return;
                }

                const noun = this.pluralizeItemLabel(selection.itemLabel, selectedIds.length);
                if (!window.confirm(`Delete ${selectedIds.length} selected ${noun}? This action cannot be undone.`)) {
                    event.preventDefault();
                    return;
                }

                selectedIds.forEach((id) => {
                    const input = document.createElement("input");
                    input.type = "hidden";
                    input.name = selection.batchInputName;
                    input.value = id;
                    idsContainer.appendChild(input);
                });
            });
        }
    },

    pluralizeItemLabel: function(label, count) {
        if (count === 1) {
            return label;
        }
        if (label.endsWith("y")) {
            return `${label.slice(0, -1)}ies`;
        }
        return `${label}s`;
    },

    getRenderedSelectionCheckboxes: function(state) {
        return Array.from(state.tableBody.querySelectorAll(state.selection.rowCheckboxSelector));
    },

    getAllSelectionCheckboxes: function(state) {
        return state.rows
            .map((row) => row.querySelector(state.selection.rowCheckboxSelector))
            .filter(Boolean);
    },

    getSelectedRowIds: function(state) {
        return this.getAllSelectionCheckboxes(state)
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) => checkbox.value);
    },

    updateSelectionState: function(state) {
        const selection = state.selection;
        const allCheckboxes = this.getAllSelectionCheckboxes(state);
        const selectedCheckboxes = allCheckboxes.filter((checkbox) => checkbox.checked);
        const renderedCheckboxes = this.getRenderedSelectionCheckboxes(state);
        const renderedChecked = renderedCheckboxes.filter((checkbox) => checkbox.checked);
        const selectAll = document.getElementById(selection.selectAllId);
        const selectedCount = document.getElementById(selection.selectedCountId);
        const deleteButton = document.getElementById(selection.deleteButtonId);

        state.rows.forEach((row) => {
            const checkbox = row.querySelector(selection.rowCheckboxSelector);
            row.classList.toggle("is-selected", Boolean(checkbox && checkbox.checked));
        });

        if (selectedCount) {
            selectedCount.textContent = String(selectedCheckboxes.length);
        }
        if (deleteButton) {
            const hasSelection = selectedCheckboxes.length > 0;
            deleteButton.disabled = !hasSelection;
            deleteButton.classList.toggle("d-none", !hasSelection);
        }
        if (selectAll) {
            selectAll.checked = renderedCheckboxes.length > 0
                && renderedChecked.length === renderedCheckboxes.length;
            selectAll.indeterminate = renderedChecked.length > 0
                && renderedChecked.length < renderedCheckboxes.length;
            selectAll.disabled = renderedCheckboxes.length === 0;
        }
    },

    sortRows: function(state, column) {
        if (!state || !column) {
            return;
        }

        if (state.sortState.column === column) {
            state.sortState.ascending = !state.sortState.ascending;
        } else {
            state.sortState.column = column;
            state.sortState.ascending = true;
        }

        state.currentPage = 1;
        this.updateSortIcons(state.tableKey);
    },

    applyCategoryFilters: function() {
        if (!this.categoryState) {
            return;
        }

        const nameFilter = (document.getElementById("categoryNameFilter")?.value || "").toLowerCase();
        const typeFilter = document.getElementById("categoryTypeFilter")?.value || "";
        const expenseFilter = document.getElementById("categoryExpenseFilter")?.value || "";
        const housingFilter = document.getElementById("categoryHousingFilter")?.value || "";

        this.categoryState.filteredRows = this.categoryState.rows.filter((row) => {
            const matchesName = row.dataset.name.includes(nameFilter);
            const matchesType = !typeFilter || row.dataset.transactionType === typeFilter;
            const matchesExpense = !expenseFilter || row.dataset.expenseType === expenseFilter;
            const matchesHousing = !housingFilter || row.dataset.isHousing === housingFilter;
            return matchesName && matchesType && matchesExpense && matchesHousing;
        });

        this.sortFilteredRows(this.categoryState, (row, column) => {
            if (column === "name") return row.dataset.name;
            if (column === "transaction_type") return row.dataset.transactionType;
            if (column === "expense_type") return row.dataset.expenseType;
            if (column === "is_housing") return row.dataset.isHousing === "yes" ? 1 : 0;
            if (column === "subcategories_count") return parseInt(row.dataset.subcategoriesCount || "0", 10);
            if (column === "transactions_count") return parseInt(row.dataset.transactionsCount || "0", 10);
            return row.dataset.name;
        });

        this.renderTable(this.categoryState);
    },

    applySubcategoryFilters: function() {
        if (!this.subcategoryState) {
            return;
        }

        const nameFilter = (document.getElementById("subcategoryNameFilter")?.value || "").toLowerCase();
        const categoryFilter = document.getElementById("subcategoryCategoryFilter")?.value || "";
        const budgetGroupFilter = document.getElementById("subcategoryBudgetGroupFilter")?.value || "";
        const expenseNatureFilter = document.getElementById("subcategoryExpenseNatureFilter")?.value || "";
        const essentialFilter = document.getElementById("subcategoryEssentialFilter")?.value || "";

        this.subcategoryState.filteredRows = this.subcategoryState.rows.filter((row) => {
            const matchesName = row.dataset.name.includes(nameFilter);
            const matchesCategory = !categoryFilter || row.dataset.parentCategoryId === categoryFilter;
            const matchesBudgetGroup = !budgetGroupFilter || row.dataset.budgetGroup === budgetGroupFilter;
            const matchesExpenseNature = !expenseNatureFilter || row.dataset.expenseNature === expenseNatureFilter;
            const matchesEssential = !essentialFilter || row.dataset.isEssential === essentialFilter;
            return matchesName && matchesCategory && matchesBudgetGroup && matchesExpenseNature && matchesEssential;
        });

        this.sortFilteredRows(this.subcategoryState, (row, column) => {
            if (column === "name") return row.dataset.name;
            if (column === "parent_category") return row.dataset.parentCategoryName;
            if (column === "budget_group") return row.dataset.budgetGroup;
            if (column === "expense_nature") return row.dataset.expenseNature;
            if (column === "is_essential") return row.dataset.isEssential === "yes" ? 1 : 0;
            if (column === "transactions_count") return parseInt(row.dataset.transactionsCount || "0", 10);
            return row.dataset.name;
        });

        this.renderTable(this.subcategoryState);
    },

    sortFilteredRows: function(state, valueGetter) {
        const { column, ascending } = state.sortState;
        if (!column) {
            return;
        }

        state.filteredRows.sort((a, b) => {
            const valA = valueGetter(a, column);
            const valB = valueGetter(b, column);

            if (window.FinOrbitTables && typeof window.FinOrbitTables.compareValues === "function") {
                return window.FinOrbitTables.compareValues(valA, valB, ascending);
            }

            if (typeof valA === "number" && typeof valB === "number") {
                return ascending ? valA - valB : valB - valA;
            }

            const aText = String(valA || "");
            const bText = String(valB || "");
            return ascending ? aText.localeCompare(bText) : bText.localeCompare(aText);
        });
    },

    updateSortIcons: function(tableKey) {
        const state = tableKey === "categories" ? this.categoryState : this.subcategoryState;

        if (window.FinOrbitTables && typeof window.FinOrbitTables.updateSortHeaders === "function") {
            window.FinOrbitTables.updateSortHeaders({
                tableKey,
                activeColumn: state && state.sortState ? state.sortState.column : null,
                ascending: state && state.sortState ? state.sortState.ascending : true,
            });
            return;
        }

        const headers = document.querySelectorAll(`.sortable-header[data-table="${tableKey}"]`);
        headers.forEach((header) => {
            const icon = header.querySelector(".sort-icon");
            if (!icon) {
                return;
            }
            icon.className = "bi bi-arrow-down-up sort-icon opacity-50";
        });

        if (!state || !state.sortState.column) {
            return;
        }

        const activeHeader = document.querySelector(
            `.sortable-header[data-table="${tableKey}"][data-sort="${state.sortState.column}"] .sort-icon`
        );
        if (!activeHeader) {
            return;
        }

        activeHeader.className = state.sortState.ascending
            ? "bi bi-sort-up sort-icon"
            : "bi bi-sort-down sort-icon";
    },

    renderTable: function(state) {
        if (!state) {
            return;
        }

        const totalRows = state.filteredRows.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / state.rowsPerPage));
        state.currentPage = Math.min(Math.max(state.currentPage, 1), totalPages);
        const start = (state.currentPage - 1) * state.rowsPerPage;
        const end = Math.min(start + state.rowsPerPage, totalRows);
        const rowsToRender = state.filteredRows.slice(start, end);

        state.tableBody.innerHTML = "";

        if (!totalRows) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td colspan="${state.emptyColspan}" class="text-center py-4 text-muted">${state.noDataMessage}</td>`;
            state.tableBody.appendChild(tr);
        } else {
            rowsToRender.forEach((row) => {
                state.tableBody.appendChild(row);
            });
        }

        const visibleCount = document.getElementById(state.visibleCountId);
        if (visibleCount) {
            visibleCount.textContent = String(totalRows);
        }

        this.renderPagination(state, totalRows, totalPages, start, end);
        this.updateSelectionState(state);
    },

    renderPagination: function(state, totalRows, totalPages, start, end) {
        const wrapper = document.getElementById(state.pagination.wrapperId);
        const info = document.getElementById(state.pagination.infoId);
        const controls = document.getElementById(state.pagination.controlsId);
        if (!wrapper || !info || !controls) {
            return;
        }

        if (totalRows <= state.rowsPerPage) {
            wrapper.classList.add("d-none");
            controls.innerHTML = "";
            info.textContent = "";
            return;
        }

        wrapper.classList.remove("d-none");
        info.textContent = `Showing ${start + 1}-${end} of ${totalRows}`;
        controls.innerHTML = "";

        controls.appendChild(
            this.buildPaginationButton("Prev", {
                disabled: state.currentPage === 1,
                onClick: () => this.changePage(state, state.currentPage - 1),
            })
        );

        const pageWindow = window.FinOrbitTables && typeof window.FinOrbitTables.getPageWindow === "function"
            ? window.FinOrbitTables.getPageWindow(totalPages, state.currentPage)
            : this.getPageWindow(totalPages, state.currentPage);

        pageWindow.forEach((entry) => {
            if (entry === "...") {
                const ellipsis = document.createElement("span");
                ellipsis.className = "pagination-ellipsis";
                ellipsis.textContent = "...";
                controls.appendChild(ellipsis);
                return;
            }

            controls.appendChild(
                this.buildPaginationButton(String(entry), {
                    active: entry === state.currentPage,
                    onClick: () => this.changePage(state, entry),
                })
            );
        });

        controls.appendChild(
            this.buildPaginationButton("Next", {
                disabled: state.currentPage === totalPages,
                onClick: () => this.changePage(state, state.currentPage + 1),
            })
        );
    },

    changePage: function(state, targetPage) {
        const totalPages = Math.max(1, Math.ceil(state.filteredRows.length / state.rowsPerPage));
        state.currentPage = Math.min(Math.max(targetPage, 1), totalPages);
        this.renderTable(state);
    },

    buildPaginationButton: function(label, options = {}) {
        if (window.FinOrbitTables && typeof window.FinOrbitTables.buildPaginationButton === "function") {
            return window.FinOrbitTables.buildPaginationButton(label, {
                ...options,
                className: "pagination-btn fo-pagination-btn",
            });
        }

        const button = document.createElement("button");
        button.type = "button";
        button.className = "pagination-btn fo-pagination-btn";
        button.textContent = label;

        if (options.active) {
            button.classList.add("is-active");
        }
        if (options.disabled) {
            button.disabled = true;
        }
        if (typeof options.onClick === "function") {
            button.addEventListener("click", options.onClick);
        }
        return button;
    },

    getPageWindow: function(totalPages, currentPage) {
        if (totalPages <= 7) {
            return Array.from({ length: totalPages }, (_, idx) => idx + 1);
        }

        const pages = [1];
        const start = Math.max(2, currentPage - 1);
        const end = Math.min(totalPages - 1, currentPage + 1);

        if (start > 2) {
            pages.push("...");
        }

        for (let page = start; page <= end; page += 1) {
            pages.push(page);
        }

        if (end < totalPages - 1) {
            pages.push("...");
        }

        pages.push(totalPages);
        return pages;
    },
};

document.addEventListener("DOMContentLoaded", () => {
    CategoryManagerModule.init();
});
