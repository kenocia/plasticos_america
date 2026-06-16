/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class DeductionsReport extends Component {
    static template = "payroll_hn.DeductionsReport";
    static props = {
        action: { type: Object, optional: true },
    };

    setup() {
        this.notification = useService("notification");

        // Obtener lot_name del contexto de la acción
        const lotName = this.props.action?.params?.lot_name || "";

        this.state = useState({
            lotText: lotName,
            employees: [],
            deductions: [],
            isLoading: false
        });

        console.log("DEBUG DEDUCTIONS JS: Componente inicializado");
        console.log("DEBUG DEDUCTIONS JS: Action props:", this.props.action);
        console.log("DEBUG DEDUCTIONS JS: Lot name from params:", lotName);

        // Si hay un lot_name en el contexto, cargar automáticamente
        if (lotName) {
            console.log("DEBUG DEDUCTIONS JS: Cargando automáticamente con lot_name:", lotName);
            this.lotSearch();
        }
    }

    async lotSearch() {
        if (!this.state.lotText.trim()) {
            this.notification.add(_t("Please enter a lot number"), { type: "warning" });
            return;
        }

        this.state.isLoading = true;

        try {
            const response = await fetch("/payroll_hn/lot_deduction_search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        data: { lot_text: this.state.lotText }
                    },
                    id: Math.floor(Math.random() * 1000000)
                })
            });

            const result = await response.json();
            const data = result.result;

            console.log("DEBUG DEDUCTIONS JS: Received data from server:", data);
            console.log("DEBUG DEDUCTIONS JS: Number of employees:", data.employees?.length || 0);
            console.log("DEBUG DEDUCTIONS JS: Deductions:", data.deductions);
            
            if (data.employees && data.employees.length > 0) {
                console.log("DEBUG DEDUCTIONS JS: First employee:", data.employees[0]);
            }

            this.state.employees = data.employees || [];
            this.state.deductions = data.deductions || [];

            this.renderTable(data);

        } catch (error) {
            console.error("Error fetching deductions data:", error);
            this.notification.add(_t("Error loading deductions data"), { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    renderTable(data) {
        const payrollTable = document.getElementById('payroll_table');
        if (!payrollTable) return;

        payrollTable.innerHTML = '';

        // Header row
        let headerRow = `
            <tr class="w-100">
                <th class="l-10 left">No.</th>
                <th class="l-10 left">Nombre y apellidos</th>
        `;

        data.deductions.forEach(function(deduction) {
            headerRow += `<th class="center">${deduction}</th>`;
        });

        headerRow += `<th class="center">Total</th></tr>`;
        payrollTable.innerHTML += headerRow;

        // Data rows
        let count = 0;
        const totals = Array(data.deductions.length).fill(0);

        data.employees.forEach(function(employee) {
            let amount = 0;
            count += 1;

            let row = `
                <tr class="w-100">
                    <td class="l-10 left">${count}</td>
                    <td class="l-10 left">${employee.employee}</td>
            `;

            employee.rules.forEach(function(rule, index) {
                if (rule.amount === -0) {
                    rule.amount = 0;
                }

                const formattedAmount = rule.amount.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                });

                row += `<td class="right r-10">${formattedAmount}</td>`;
                amount += rule.amount;
                totals[index] += rule.amount;
            });

            const formattedTotalAmount = amount.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });

            row += `<td class="right r-10">${formattedTotalAmount}</td></tr>`;
            payrollTable.innerHTML += row;
        });

        // Totals row
        let totalAmount = 0;
        let totalsRow = `
            <tr class="w-100">
                <th colspan="2" class="center">Totales</th>
        `;

        totals.forEach(function(total) {
            const formattedTotal = total.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            totalAmount += total;
            totalsRow += `<th class="right r-10">${formattedTotal}</th>`;
        });

        const formattedAmountTotal = totalAmount.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });

        totalsRow += `<th class="right r-10">${formattedAmountTotal}</th></tr>`;
        payrollTable.innerHTML += totalsRow;
    }

    onLotTextChange(ev) {
        this.state.lotText = ev.target.value;
    }
}

registry.category("actions").add("deductions_report", DeductionsReport);