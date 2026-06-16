/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { KcSalesDashboard } from "../sales_dashboard/sales_dashboard";
import { KcInventoryDashboard } from "../inventory_dashboard/inventory_dashboard";
import { KcMovementsDashboard } from "../movements_dashboard/movements_dashboard";

const DEFAULT_DASHBOARDS = [
    { id: "sales", name: "Ventas", icon: "fa-line-chart" },
    { id: "general_inventory", name: "Inventario General", icon: "fa-cubes" },
    { id: "inventory_movements", name: "Movimientos de inventario", icon: "fa-exchange" },
];

export class KcDashboardApp extends Component {
    static template = "kc_dashboards.DashboardApp";
    static components = { KcSalesDashboard, KcInventoryDashboard, KcMovementsDashboard };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.dash = useState({
            dashboards: DEFAULT_DASHBOARDS,
            activeDashboard: "sales",
            activeDashboardLabel: DEFAULT_DASHBOARDS[0].name,
            sidebarOpen: false,
        });

        onWillStart(async () => {
            try {
                const items = await this.orm.call(
                    "kc.dashboard",
                    "get_kc_dashboard_items",
                    []
                );
                if (items?.length) {
                    this.dash.dashboards = items;
                    this._syncActiveLabel();
                }
            } catch {
                this.dash.dashboards = DEFAULT_DASHBOARDS;
                this._syncActiveLabel();
            }
        });
    }

    _syncActiveLabel() {
        const active = this.dash.dashboards.find(
            (item) => item.id === this.dash.activeDashboard
        );
        this.dash.activeDashboardLabel = active?.name || "Dashboard";
    }

    toggleSidebar() {
        this.dash.sidebarOpen = !this.dash.sidebarOpen;
    }

    closeSidebar() {
        this.dash.sidebarOpen = false;
    }

    isActive(dashboardId) {
        return this.dash.activeDashboard === dashboardId;
    }

    onSelectDashboard(dashboardId) {
        this.dash.activeDashboard = dashboardId;
        this._syncActiveLabel();
        this.closeSidebar();
    }

    async onBackToHome() {
        this.closeSidebar();
        const homeMenu = this.env.services.home_menu;
        if (homeMenu?.toggle) {
            await homeMenu.toggle(true);
            return;
        }
        browser.location.href = "/odoo";
    }
}

registry.category("actions").add("kc_dashboards_app", KcDashboardApp);
