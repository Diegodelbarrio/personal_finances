(function (window, document) {
    "use strict";

    const SORT_DEFAULT = "bi bi-arrow-down-up sort-icon opacity-50";
    const SORT_ASC = "bi bi-sort-up sort-icon";
    const SORT_DESC = "bi bi-sort-down sort-icon";

    const FinOrbitTables = {
        init(root = document) {
            this.refreshScrollShadows(root);
            this.bindScrollShadows(root);
            this.initActionDropdowns(root);
        },

        getPageWindow(totalPages, currentPage, maxVisible = 7) {
            if (totalPages <= maxVisible) {
                return Array.from({ length: totalPages }, (_, index) => index + 1);
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

        compareValues(a, b, ascending = true) {
            const aIsNumber = typeof a === "number" && Number.isFinite(a);
            const bIsNumber = typeof b === "number" && Number.isFinite(b);

            if (aIsNumber && bIsNumber) {
                return ascending ? a - b : b - a;
            }

            const aText = String(a || "");
            const bText = String(b || "");
            return ascending ? aText.localeCompare(bText) : bText.localeCompare(aText);
        },

        buildPaginationButton(label, options = {}) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = options.className || "fo-pagination-btn";
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

        updateSortHeaders(options = {}) {
            const {
                container = document,
                tableKey = null,
                activeColumn = null,
                ascending = true,
                headerSelector = ".sortable-header",
                iconSelector = ".sort-icon, i",
                defaultIconClass = SORT_DEFAULT,
                ascIconClass = SORT_ASC,
                descIconClass = SORT_DESC,
            } = options;

            const scopedSelector = tableKey
                ? `${headerSelector}[data-table="${tableKey}"]`
                : headerSelector;

            container.querySelectorAll(scopedSelector).forEach((header) => {
                header.setAttribute("aria-sort", "none");
                const icon = header.querySelector(iconSelector);
                if (icon) {
                    icon.className = defaultIconClass;
                }
            });

            if (!activeColumn) {
                return;
            }

            const activeSelector = tableKey
                ? `${headerSelector}[data-table="${tableKey}"][data-sort="${activeColumn}"]`
                : `${headerSelector}[data-sort="${activeColumn}"]`;
            const activeHeader = container.querySelector(activeSelector);
            if (!activeHeader) {
                return;
            }

            activeHeader.setAttribute("aria-sort", ascending ? "ascending" : "descending");
            const activeIcon = activeHeader.querySelector(iconSelector);
            if (activeIcon) {
                activeIcon.className = ascending ? ascIconClass : descIconClass;
            }
        },

        initActionDropdowns(root = document, selector = '.fo-table-actions-trigger[data-bs-toggle="dropdown"], .quick-actions-trigger[data-bs-toggle="dropdown"]') {
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

            root.querySelectorAll(selector).forEach((trigger) => {
                bootstrap.Dropdown.getOrCreateInstance(trigger, {
                    popperConfig(defaultConfig) {
                        const baseConfig = defaultConfig || {};
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

        bindScrollShadows(root = document) {
            root.querySelectorAll(".fo-table-responsive").forEach((scroller) => {
                if (scroller.dataset.foScrollBound === "true") {
                    return;
                }
                scroller.dataset.foScrollBound = "true";
                scroller.addEventListener("scroll", () => this.updateScrollShadow(scroller), { passive: true });
            });

            if (!this._resizeBound) {
                this._resizeBound = true;
                window.addEventListener("resize", () => this.refreshScrollShadows(document), { passive: true });
            }
        },

        refreshScrollShadows(root = document) {
            root.querySelectorAll(".fo-table-responsive").forEach((scroller) => {
                this.updateScrollShadow(scroller);
            });
        },

        updateScrollShadow(scroller) {
            const shell = scroller.closest(".fo-table-shell");
            if (!shell) {
                return;
            }

            const maxScroll = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
            shell.classList.toggle("is-scrollable-left", scroller.scrollLeft > 0);
            shell.classList.toggle("is-scrollable-right", scroller.scrollLeft < maxScroll - 1);
        },
    };

    window.FinOrbitTables = FinOrbitTables;

    document.addEventListener("DOMContentLoaded", () => {
        FinOrbitTables.init();
    });
})(window, document);
