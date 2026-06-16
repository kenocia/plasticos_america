/** @odoo-module **/

import { Component, mount } from "@odoo/owl";
import { ExpenseForm } from "./expense_owl";

// Inicializar componente de gastos cuando se carga la página
document.addEventListener('DOMContentLoaded', function() {
    const expenseFormContainer = document.getElementById('expense_form_container');
    if (expenseFormContainer) {
        mount(ExpenseForm, expenseFormContainer);
    }
});

// Funcionalidad de filtros y búsqueda
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('expense_search');
    const statusFilter = document.getElementById('status_filter');
    const dateFilter = document.getElementById('date_filter');
    const selectAllCheckbox = document.getElementById('select_all');
    const expenseCheckboxes = document.querySelectorAll('.expense-checkbox');
    
    // Filtro de búsqueda
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterExpenses();
        });
    }
    
    // Filtro de estado
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            filterExpenses();
        });
    }
    
    // Filtro de fecha
    if (dateFilter) {
        dateFilter.addEventListener('change', function() {
            filterExpenses();
        });
    }
    
    // Seleccionar todos
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            expenseCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });
    }
    
    function filterExpenses() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const statusValue = statusFilter ? statusFilter.value : '';
        const dateValue = dateFilter ? dateFilter.value : '';
        
        const rows = document.querySelectorAll('.expense-row');
        
        rows.forEach(row => {
            const name = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const description = row.querySelector('td:nth-child(3)').textContent.toLowerCase();
            const status = row.getAttribute('data-status');
            
            let showRow = true;
            
            // Filtro de búsqueda
            if (searchTerm && !name.includes(searchTerm) && !description.includes(searchTerm)) {
                showRow = false;
            }
            
            // Filtro de estado
            if (statusValue && status !== statusValue) {
                showRow = false;
            }
            
            // Filtro de fecha (implementar lógica según necesidad)
            if (dateValue) {
                // Implementar lógica de filtro por fecha
            }
            
            row.style.display = showRow ? '' : 'none';
        });
    }
});
