/** @odoo-module **/

import { Component, mount } from "@odoo/owl";
import { LeaveRequestForm } from "./leave_owl";

// Inicializar componente de ausencias cuando se carga la página
document.addEventListener('DOMContentLoaded', function() {
    const leaveFormContainer = document.getElementById('leave_form_container');
    if (leaveFormContainer) {
        mount(LeaveRequestForm, leaveFormContainer);
    }
});

// Funcionalidad de filtros y búsqueda para ausencias
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('leave_search');
    const statusFilter = document.getElementById('status_filter');
    const typeFilter = document.getElementById('type_filter');
    const clearFiltersBtn = document.getElementById('clear_filters');
    
    // Filtro de búsqueda
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterLeaves();
        });
    }
    
    // Filtro de estado
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            filterLeaves();
        });
    }
    
    // Filtro de tipo
    if (typeFilter) {
        typeFilter.addEventListener('change', function() {
            filterLeaves();
        });
    }
    
    // Limpiar filtros
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', function() {
            if (searchInput) searchInput.value = '';
            if (statusFilter) statusFilter.value = '';
            if (typeFilter) typeFilter.value = '';
            filterLeaves();
        });
    }
    
    function filterLeaves() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const statusValue = statusFilter ? statusFilter.value : '';
        const typeValue = typeFilter ? typeFilter.value : '';
        
        const rows = document.querySelectorAll('.leave-row');
        
        rows.forEach(row => {
            const typeName = row.querySelector('td:nth-child(1)').textContent.toLowerCase();
            const status = row.getAttribute('data-status');
            
            let showRow = true;
            
            // Filtro de búsqueda
            if (searchTerm && !typeName.includes(searchTerm)) {
                showRow = false;
            }
            
            // Filtro de estado
            if (statusValue && status !== statusValue) {
                showRow = false;
            }
            
            // Filtro de tipo (implementar según necesidad)
            if (typeValue) {
                // Implementar lógica de filtro por tipo
            }
            
            row.style.display = showRow ? '' : 'none';
        });
    }
    
    // Cargar tipos de ausencia para el filtro
    loadLeaveTypes();
    
    async function loadLeaveTypes() {
        try {
            const response = await fetch('/get_leave_types', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            });
            
            const leaveTypes = await response.json();
            
            if (typeFilter && leaveTypes.length > 0) {
                // Limpiar opciones existentes excepto la primera
                typeFilter.innerHTML = '<option value="">Todos los tipos</option>';
                
                leaveTypes.forEach(leaveType => {
                    const option = document.createElement('option');
                    option.value = leaveType.id;
                    option.textContent = leaveType.name;
                    typeFilter.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error cargando tipos de ausencia:', error);
        }
    }
});
