/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

export class KcMovementsDashboard extends Component {
    static template = "kc_dashboards.MovementsDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            loading: true,
            data: null,
            error: null,
            filterOptions: {
                locations: [],
                movement_types: [],
            },
            filters: {
                date_from: "",
                date_to: "",
                location_id: "",
                product_id: "",
                movement_type: "",
            },
            productSearch: "",
            productResults: [],
            showProductDropdown: false,
            productSearchLoading: false,
            page: 1,
            filtersOpen: false,
        });

        this._productSearchTimeout = null;

        onMounted(() => {
            this.loadDashboard();
        });
    }

    async loadFilterOptions() {
        try {
            this.state.filterOptions = await this.orm.call(
                "stock.move",
                "get_movements_dashboard_filter_options",
                []
            );
        } catch {
            this.state.filterOptions = {
                locations: [],
                movement_types: [],
            };
        }
    }

    async searchProducts() {
        const query = (this.state.productSearch || "").trim();
        if (!query) {
            this.state.productResults = [];
            this.state.showProductDropdown = false;
            return;
        }
        this.state.productSearchLoading = true;
        try {
            this.state.productResults = await this.orm.call(
                "stock.move",
                "search_movements_dashboard_products",
                [],
                { query, limit: 30 }
            );
            this.state.showProductDropdown = true;
        } catch {
            this.state.productResults = [];
        } finally {
            this.state.productSearchLoading = false;
        }
    }

    onProductSearchInput(ev) {
        this.state.productSearch = ev.target.value;
        this.state.filters.product_id = "";
        clearTimeout(this._productSearchTimeout);
        if (!this.state.productSearch.trim()) {
            this.state.productResults = [];
            this.state.showProductDropdown = false;
            return;
        }
        this._productSearchTimeout = setTimeout(() => this.searchProducts(), 250);
    }

    onProductSearchFocus() {
        if (this.state.productSearch.trim()) {
            this.searchProducts();
        }
    }

    onProductSearchBlur() {
        setTimeout(() => {
            this.state.showProductDropdown = false;
        }, 150);
    }

    onSelectProduct(product) {
        this.state.filters.product_id = String(product.id);
        this.state.productSearch = product.name;
        this.state.showProductDropdown = false;
    }

    onClearProductSearch() {
        this.state.filters.product_id = "";
        this.state.productSearch = "";
        this.state.productResults = [];
        this.state.showProductDropdown = false;
    }

    getActiveFilters() {
        const filters = {};
        if (this.state.filters.date_from) {
            filters.date_from = this.state.filters.date_from;
        }
        if (this.state.filters.date_to) {
            filters.date_to = this.state.filters.date_to;
        }
        if (this.state.filters.location_id) {
            filters.location_id = parseInt(this.state.filters.location_id, 10);
        }
        if (this.state.filters.product_id) {
            filters.product_id = parseInt(this.state.filters.product_id, 10);
        }
        if (this.state.filters.movement_type) {
            filters.movement_type = this.state.filters.movement_type;
        }
        return filters;
    }

    async loadDashboard(page = this.state.page) {
        this.state.loading = true;
        this.state.error = null;
        try {
            await this.loadFilterOptions();
            const data = await this.orm.call(
                "stock.move",
                "get_movements_dashboard_data",
                [],
                {
                    filters: this.getActiveFilters(),
                    page,
                    page_size: 8,
                }
            );
            this.state.data = data;
            this.state.page = page;
            if (!this.state.filters.date_from && data.filters?.date_from) {
                this.state.filters.date_from = data.filters.date_from;
            }
            if (!this.state.filters.date_to && data.filters?.date_to) {
                this.state.filters.date_to = data.filters.date_to;
            }
        } catch (error) {
            console.error("kc_dashboards movements load error:", error);
            this.state.error =
                error?.data?.message ||
                error?.message ||
                "No se pudo cargar el dashboard.";
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    onFilterChange(field, ev) {
        this.state.filters[field] = ev.target.value;
    }

    toggleFilters() {
        this.state.filtersOpen = !this.state.filtersOpen;
    }

    async onApplyFilters() {
        this.state.page = 1;
        await this.loadDashboard(1);
    }

    async onClearFilters() {
        const today = this.state.data?.filters?.date_to || this.state.data?.filters?.date_from || "";
        this.state.filters = {
            date_from: today,
            date_to: today,
            location_id: "",
            product_id: "",
            movement_type: "",
        };
        this.onClearProductSearch();
        this.state.page = 1;
        await this.loadDashboard(1);
    }

    async onRefresh() {
        await this.loadDashboard(this.state.page);
    }

    async onDrillDown(drillType, drillValue = null) {
        const action = await this.orm.call(
            "stock.move",
            "get_movements_dashboard_drilldown_action",
            [],
            {
                drill_type: drillType,
                drill_value: drillValue,
                filters: this.getActiveFilters(),
            }
        );
        if (action) {
            this.actionService.doAction(action);
        }
    }

    async onOpenMove(moveId) {
        await this.onDrillDown("move", moveId);
    }

    async onChangePage(page) {
        if (page < 1 || page > (this.state.data?.lines?.total_pages || 1)) {
            return;
        }
        await this.loadDashboard(page);
    }

    getDeltaClass(delta) {
        return delta >= 0 ? "kc-dash-kpi__delta--up" : "kc-dash-kpi__delta--down";
    }

    getDeltaIcon(delta) {
        return delta >= 0 ? "fa-arrow-up" : "fa-arrow-down";
    }

    formatDeltaAbs(delta) {
        return Math.abs(Number(delta || 0)).toFixed(1);
    }

    formatDisplayDate(isoDate) {
        if (!isoDate) {
            return "período anterior";
        }
        const parts = isoDate.split("-");
        if (parts.length !== 3) {
            return isoDate;
        }
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }

    formatComparisonPeriod() {
        const filters = this.state.data?.filters || {};
        const from = this.formatDisplayDate(filters.previous_date_from);
        const to = this.formatDisplayDate(filters.previous_date_to);
        if (!filters.previous_date_from) {
            return "período anterior";
        }
        if (filters.previous_date_from === filters.previous_date_to) {
            return from;
        }
        return `${from} - ${to}`;
    }

    getKpiComparison(kpiKey) {
        const kpi = this.state.data?.kpis?.[kpiKey];
        if (!kpi) {
            return "";
        }
        const prevDate = this.formatComparisonPeriod();
        let previousLabel;
        if (kpiKey === "total_qty") {
            previousLabel = kpi.previous || "";
        } else {
            previousLabel = String(kpi.previous ?? 0);
        }
        return `vs. ${prevDate} (${previousLabel})`;
    }

    getPageNumbers() {
        const totalPages = this.state.data?.lines?.total_pages || 1;
        const current = this.state.data?.lines?.page || 1;
        const pages = [];
        const start = Math.max(1, current - 2);
        const end = Math.min(totalPages, start + 4);
        for (let p = start; p <= end; p += 1) {
            pages.push(p);
        }
        return pages;
    }

    formatPct(value) {
        return `${Number(value || 0).toFixed(1)}%`;
    }

    getPaginationLabel() {
        const lines = this.state.data?.lines || {};
        if (!lines.total) {
            return "0";
        }
        const from = ((lines.page - 1) * lines.page_size) + 1;
        const to = Math.min(lines.page * lines.page_size, lines.total);
        return `${from} a ${to} de ${lines.total}`;
    }

    getTypeColor(index) {
        const colors = ["#40c057", "#fa5252", "#4c6ef5"];
        return colors[index % colors.length];
    }

    getDonutGradient() {
        const types = this.state.data?.movements_by_type || [];
        if (!types.length) {
            return "conic-gradient(#dee2e6 0deg 360deg)";
        }
        let current = 0;
        const colors = ["#40c057", "#fa5252", "#4c6ef5"];
        const segments = types.map((item, index) => {
            const start = current;
            current += item.pct * 3.6;
            return `${colors[index % colors.length]} ${start}deg ${current}deg`;
        });
        return `conic-gradient(${segments.join(", ")})`;
    }

    isSelected(field, value) {
        return String(this.state.filters[field] || "") === String(value || "");
    }

    _buildTrendLinePath(points) {
        if (!points.length) {
            return "";
        }
        let path = `M ${points[0].x} ${points[0].y}`;
        for (let i = 1; i < points.length; i += 1) {
            const prev = points[i - 1];
            const curr = points[i];
            const ctrlX = (prev.x + curr.x) / 2;
            path += ` C ${ctrlX} ${prev.y}, ${ctrlX} ${curr.y}, ${curr.x} ${curr.y}`;
        }
        return path;
    }

    formatQtyShort(qty) {
        const value = Number(qty || 0);
        if (value >= 1000000) {
            return `${(value / 1000000).toFixed(1).replace(/\.0$/, "")}M`;
        }
        if (value >= 1000) {
            return `${Math.round(value / 1000)}K`;
        }
        return String(Math.round(value));
    }

    get trendChart() {
        const trend = this.state.data?.movements_trend?.points || [];
        const amounts = trend.map((point) => Math.max(Number(point.qty) || 0, 0));
        const yMax = Math.max(...amounts, 1);
        const width = 560;
        const height = 200;
        const pad = { top: 30, right: 0, bottom: 14, left: 0 };
        const chartTop = pad.top;
        const chartBottom = height - pad.bottom;
        const chartLeft = pad.left;
        const chartRight = width - pad.right;
        const chartHeight = chartBottom - chartTop;
        const chartWidth = chartRight - chartLeft;
        const tickCount = 5;

        const yTicks = [];
        for (let i = tickCount; i >= 0; i -= 1) {
            const value = (yMax / tickCount) * i;
            yTicks.push({
                value,
                label: this.formatQtyShort(value),
                y: chartTop + chartHeight - (value / yMax) * chartHeight,
            });
        }

        const gridLines = yTicks.map((tick) => ({
            y: tick.y,
            x1: chartLeft,
            x2: chartRight,
        }));

        const slotCount = Math.max(trend.length - 1, 1);
        const points = trend.map((point, index) => {
            const qty = Math.max(Number(point.qty) || 0, 0);
            const x = chartLeft + (index / slotCount) * chartWidth;
            const rawY = chartBottom - (qty / yMax) * chartHeight;
            const y = Math.min(Math.max(rawY, chartTop), chartBottom);
            return { label: point.label, x, y };
        });

        const linePath = this._buildTrendLinePath(points);
        const areaPath = points.length
            ? `${linePath} L ${points[points.length - 1].x} ${chartBottom} L ${points[0].x} ${chartBottom} Z`
            : "";

        return {
            points,
            linePath,
            areaPath,
            yTicks,
            gridLines,
            viewBox: `0 0 ${width} ${height}`,
            chartTop,
            chartBottom,
        };
    }

    getTrendXAxisStyle() {
        const count = Math.max((this.state.data?.movements_trend?.points || []).length, 1);
        return `grid-template-columns: repeat(${count}, minmax(0, 1fr))`;
    }
}
