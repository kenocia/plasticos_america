/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class PayrollReport extends Component {
    static template = "payroll_hn.PayrollReport";
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
            benefits: [],
            deductions: [],
            isLoading: false
        });

        console.log("DEBUG JS: Componente inicializado");
        console.log("DEBUG JS: Action props:", this.props.action);
        console.log("DEBUG JS: Lot name from params:", lotName);

        // Si hay un lot_name en el contexto, cargar automáticamente
        if (lotName) {
            console.log("DEBUG JS: Cargando automáticamente con lot_name:", lotName);
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
            const response = await fetch("/payroll_hn/lot_search", {
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

            console.log("DEBUG JS: Received data from server:", data);
            console.log("DEBUG JS: Number of employees:", data.employees?.length || 0);
            console.log("DEBUG JS: Benefits:", data.benefits);
            console.log("DEBUG JS: Deductions:", data.deductions);
            
            if (data.employees && data.employees.length > 0) {
                console.log("DEBUG JS: First employee:", data.employees[0]);
            }

            this.state.employees = data.employees || [];
            this.state.benefits = data.benefits || [];
            this.state.deductions = data.deductions || [];

            this.renderTable(data);

        } catch (error) {
            console.error("Error fetching payroll data:", error);
            this.notification.add(_t("Error loading payroll data"), { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async exportXlsx() {
        if (!this.state.lotText.trim()) {
            this.notification.add(_t("Please enter a lot number"), { type: "warning" });
            return;
        }

        try {
            const response = await fetch("/payroll_hn/export_xlsx", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        data: JSON.stringify({ lot_text: this.state.lotText })
                    },
                    id: Math.floor(Math.random() * 1000000)
                })
            });

            const result = await response.json();
            const data = result.result;

            if (data.url) {
                window.location.href = data.url;
            } else {
                this.notification.add(_t("Could not generate file"), { type: "danger" });
            }
        } catch (error) {
            console.error("Error exporting to Excel:", error);
            this.notification.add(_t("Error exporting to Excel"), { type: "danger" });
        }
    }

    renderTable(data) {
        const payrollTable = document.getElementById('payroll_table');
        if (!payrollTable) return;

        payrollTable.innerHTML = '';

        // Header rows
        let headerRow = `
            <tr class="w-100">
                <th rowspan="2" class="l-10 left">No.</th>
                <th rowspan="2" class="l-10 left">Nombre y apellidos</th>
                <th rowspan="2" class="center">Salario base</th>
        `;

        // Benefits header
        if (data.benefits.length > 0) {
            headerRow += `<th colspan="${data.benefits.length}" class="center">Beneficios</th>`;
        }

        headerRow += `
                <th rowspan="2" class="center">Salario bruto</th>
                <th colspan="${data.deductions.length}" class="center">Deducciones</th>
                <th rowspan="2" class="center">Total Deducciones</th>
                <th rowspan="2" class="center">Salario Neto</th>
            </tr>
        `;

        // Second header row
        headerRow += `<tr class="w-100">`;

        data.benefits.forEach(function(benefit) {
            headerRow += `<th class="center">${benefit}</th>`;
        });

        data.deductions.forEach(function(deduction) {
            headerRow += `<th class="center">${deduction}</th>`;
        });

        headerRow += `</tr>`;
        payrollTable.innerHTML += headerRow;

        // Data rows
        let count = 0;
        const totalsBenefits = Array(data.benefits.length).fill(0);
        const totalsDeductions = Array(data.deductions.length).fill(0);

        let totalSalaryBasic = 0;
        let totalSalaryGross = 0;
        let totalSalaryNet = 0;

        data.employees.forEach(function(employee) {
            totalSalaryBasic += employee.salary;

            let salaryGross = employee.salary;
            count += 1;

            const formattedAmountSalary = employee.salary.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });

            let row = `
                <tr class="w-100">
                    <td class="l-10 left">${count}</td>
                    <td class="l-10 left">${employee.employee}</td>
                    <td class="right r-10">${formattedAmountSalary}</td>
            `;

            // Benefits
            if (employee.rules && employee.rules[0] && employee.rules[0].benefits) {
                employee.rules[0].benefits.forEach(function(rule, index) {
                    const formattedAmount = rule.amount.toLocaleString('en-US', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    });
                    salaryGross += rule.amount;
                    row += `<td class="right r-10">${formattedAmount}</td>`;
                    totalsBenefits[index] += rule.amount;
                });
            }

            const formattedSalaryGross = salaryGross.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            row += `<td class="right r-10">${formattedSalaryGross}</td>`;

            totalSalaryGross += salaryGross;

            // Deductions
            if (employee.rules && employee.rules[0] && employee.rules[0].deductions) {
                employee.rules[0].deductions.forEach(function(rule, index) {
                    const formattedAmount = rule.amount.toLocaleString('en-US', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    });
                    row += `<td class="right r-10">${formattedAmount}</td>`;
                    totalsDeductions[index] += rule.amount;
                });
            }

            // Total Deducciones
            const totalDeductions = employee.total_deductions || 0;
            const formattedTotalDeductions = totalDeductions.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            row += `<td class="right r-10">${formattedTotalDeductions}</td>`;

            // Salario Neto (usar el valor calculado del servidor)
            const salaryNet = employee.net_salary || 0;
            totalSalaryNet += salaryNet;
            const formattedSalaryNet = salaryNet.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });

            row += `<td class="right r-10">${formattedSalaryNet}</td></tr>`;
            payrollTable.innerHTML += row;
        });

        // Totals row
        let totalsRow = `
            <tr class="w-100">
                <th colspan="2" class="center">Totales</th>
        `;

        const formattedTotalSalaryBasic = totalSalaryBasic.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });

        totalsRow += `<th class="right r-10">${formattedTotalSalaryBasic}</th>`;

        totalsBenefits.forEach(function(total) {
            const formattedTotal = total.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            totalsRow += `<th class="right r-10">${formattedTotal}</th>`;
        });

        const formattedTotalSalaryGross = totalSalaryGross.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });

        totalsRow += `<th class="right r-10">${formattedTotalSalaryGross}</th>`;

        totalsDeductions.forEach(function(total) {
            const formattedTotal = total.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            });
            totalsRow += `<th class="right r-10">${formattedTotal}</th>`;
        });

        // Total de todas las deducciones
        const totalAllDeductions = totalsDeductions.reduce((sum, total) => sum + total, 0);
        const formattedTotalAllDeductions = totalAllDeductions.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        totalsRow += `<th class="right r-10">${formattedTotalAllDeductions}</th>`;

        const formattedTotalSalaryNet = totalSalaryNet.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });

        totalsRow += `<th class="right r-10">${formattedTotalSalaryNet}</th></tr>`;
        payrollTable.innerHTML += totalsRow;
    }

    onLotTextChange(ev) {
        this.state.lotText = ev.target.value;
    }
}

registry.category("actions").add("payroll_report", PayrollReport);