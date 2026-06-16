/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

export class KcSalesDashboard extends Component {
    static template = "kc_dashboards.SalesDashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            loading: true,
            data: null,
            error: null,
            filters: {
                date_from: "",
                date_to: "",
                partner_id: "",
            },
            partnerSearch: "",
            partnerResults: [],
            showPartnerDropdown: false,
            partnerSearchLoading: false,
            page: 1,
            filtersOpen: false,
        });

        this._partnerSearchTimeout = null;

        onMounted(() => {
            this.loadDashboard();
        });
    }

    async searchPartners() {
        const query = (this.state.partnerSearch || "").trim();
        if (!query) {
            this.state.partnerResults = [];
            this.state.showPartnerDropdown = false;
            return;
        }
        this.state.partnerSearchLoading = true;
        try {
            this.state.partnerResults = await this.orm.call(
                "sale.order",
                "search_sales_dashboard_partners",
                [],
                { query, limit: 30 }
            );
            this.state.showPartnerDropdown = true;
        } catch {
            this.state.partnerResults = [];
        } finally {
            this.state.partnerSearchLoading = false;
        }
    }

    onPartnerSearchInput(ev) {
        this.state.partnerSearch = ev.target.value;
        this.state.filters.partner_id = "";
        clearTimeout(this._partnerSearchTimeout);
        if (!this.state.partnerSearch.trim()) {
            this.state.partnerResults = [];
            this.state.showPartnerDropdown = false;
            return;
        }
        this._partnerSearchTimeout = setTimeout(() => this.searchPartners(), 250);
    }

    onPartnerSearchFocus() {
        if (this.state.partnerSearch.trim()) {
            this.searchPartners();
        }
    }

    onPartnerSearchBlur() {
        setTimeout(() => {
            this.state.showPartnerDropdown = false;
        }, 150);
    }

    onSelectPartner(partner) {
        this.state.filters.partner_id = String(partner.id);
        this.state.partnerSearch = partner.name;
        this.state.showPartnerDropdown = false;
    }

    onClearPartnerSearch() {
        this.state.filters.partner_id = "";
        this.state.partnerSearch = "";
        this.state.partnerResults = [];
        this.state.showPartnerDropdown = false;
    }

    getActiveFilters() {
        const filters = {};
        if (this.state.filters.date_from) {
            filters.date_from = this.state.filters.date_from;
        }
        if (this.state.filters.date_to) {
            filters.date_to = this.state.filters.date_to;
        }
        if (this.state.filters.partner_id) {
            filters.partner_id = parseInt(this.state.filters.partner_id, 10);
        }
        return filters;
    }

    async loadDashboard(page = this.state.page) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call(
                "sale.order",
                "get_sales_dashboard_data",
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
            if (data.filters?.partner_id && data.filters?.partner_name) {
                this.state.filters.partner_id = String(data.filters.partner_id);
                this.state.partnerSearch = data.filters.partner_name;
            }
        } catch (error) {
            console.error("kc_dashboards load error:", error);
            this.state.error = error?.message || "No se pudo cargar el dashboard.";
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
            partner_id: "",
        };
        this.onClearPartnerSearch();
        this.state.page = 1;
        await this.loadDashboard(1);
    }

    async onRefresh() {
        await this.loadDashboard(this.state.page);
    }

    async onDrillDown(drillType, drillValue = null) {
        const action = await this.orm.call(
            "sale.order",
            "get_sales_dashboard_drilldown_action",
            [],
            {
                drill_type: drillType,
                drill_value: drillValue,
                filters: this.getActiveFilters(),
            }
        );
        this.actionService.doAction(action);
    }

    async onOpenOrder(orderId) {
        await this.onDrillDown("order", orderId);
    }

    async onChangePage(page) {
        if (page < 1 || page > (this.state.data?.orders?.total_pages || 1)) {
            return;
        }
        await this.loadDashboard(page);
    }

    formatHourAmountShort(amount) {
        const value = Number(amount || 0);
        if (value >= 1000000) {
            return `${(value / 1000000).toFixed(1).replace(/\.0$/, "")}M`;
        }
        if (value >= 1000) {
            return `${Math.round(value / 1000)}K`;
        }
        return String(Math.round(value));
    }

    getHourYMax(amounts) {
        const maxAmount = Math.max(...amounts, 0);
        if (maxAmount <= 0) {
            return 250000;
        }
        const rawStep = maxAmount / 5;
        const magnitude = 10 ** Math.floor(Math.log10(rawStep));
        const normalized = rawStep / magnitude;
        let niceStep;
        if (normalized <= 1) {
            niceStep = 1;
        } else if (normalized <= 2) {
            niceStep = 2;
        } else if (normalized <= 5) {
            niceStep = 5;
        } else {
            niceStep = 10;
        }
        return niceStep * magnitude * 5;
    }

    _buildHourLinePath(points) {
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

    get salesTrendChart() {
        const points = this.state.data?.sales_trend?.points || [];
        const amounts = points.map((point) => point.amount);
        const yMax = this.getHourYMax(amounts);
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
                label: this.formatHourAmountShort(value),
                y: chartTop + chartHeight - (value / yMax) * chartHeight,
            });
        }

        const gridLines = yTicks.map((tick) => ({
            y: tick.y,
            x1: chartLeft,
            x2: chartRight,
        }));

        const slotCount = Math.max(points.length - 1, 1);
        const chartPoints = points.map((point, index) => {
            const x = chartLeft + (index / slotCount) * chartWidth;
            const y = chartBottom - (point.amount / yMax) * chartHeight;
            return {
                key: point.key,
                label: point.label,
                amount_fmt: point.amount_fmt,
                labelShort: this.formatHourAmountShort(point.amount),
                x,
                y,
                xPct: (x / width) * 100,
                yPct: (y / height) * 100,
                labelPct: Math.max(((y - 12) / height) * 100, 2),
            };
        });

        const linePath = this._buildHourLinePath(chartPoints);
        const areaPath = chartPoints.length
            ? `${linePath} L ${chartPoints[chartPoints.length - 1].x} ${chartBottom} L ${chartPoints[0].x} ${chartBottom} Z`
            : "";

        return {
            points: chartPoints,
            linePath,
            areaPath,
            yTicks,
            gridLines,
            viewBox: `0 0 ${width} ${height}`,
            chartBottom,
        };
    }

    showTrendValueLabels() {
        return (this.state.data?.sales_trend?.points || []).length <= 15;
    }

    getTrendXAxisStyle() {
        const count = Math.max((this.state.data?.sales_trend?.points || []).length, 1);
        return `grid-template-columns: repeat(${count}, minmax(0, 1fr))`;
    }

    async onTrendDrillDown(point) {
        const granularity = this.state.data?.sales_trend?.granularity || "hour";
        const drillType = granularity === "hour" ? "hour" : `trend_${granularity}`;
        await this.onDrillDown(drillType, point.key);
    }

    getDonutGradient() {
        const channels = this.state.data?.sales_by_channel || [];
        if (!channels.length) {
            return "conic-gradient(#dee2e6 0deg 360deg)";
        }
        let current = 0;
        const colors = ["#4c6ef5", "#40c057", "#fab005", "#845ef7", "#ff6b6b"];
        const segments = channels.map((item, index) => {
            const start = current;
            current += item.pct * 3.6;
            return `${colors[index % colors.length]} ${start}deg ${current}deg`;
        });
        return `conic-gradient(${segments.join(", ")})`;
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
        if (kpiKey === "invoiced_orders") {
            return `vs. no facturadas (${kpi.non_invoiced ?? 0})`;
        }
        const prevDate = this.formatComparisonPeriod();
        let previousLabel;
        if (kpiKey === "sales") {
            previousLabel = kpi.previous?.formatted || "";
        } else {
            previousLabel = String(kpi.previous ?? 0);
        }
        return `vs. ${prevDate} (${previousLabel})`;
    }

    getPageNumbers() {
        const totalPages = this.state.data?.orders?.total_pages || 1;
        const current = this.state.data?.orders?.page || 1;
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
        const orders = this.state.data?.orders || {};
        if (!orders.total) {
            return "0";
        }
        const from = ((orders.page - 1) * orders.page_size) + 1;
        const to = Math.min(orders.page * orders.page_size, orders.total);
        return `${from} a ${to} de ${orders.total}`;
    }

    getChannelColor(index) {
        const colors = ["#4c6ef5", "#40c057", "#fab005", "#845ef7", "#ff6b6b"];
        return colors[index % colors.length];
    }
}
