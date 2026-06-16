/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class LeaveRequestForm extends Component {
    static template = "l10n_hn_hr_holidays_portal.LeaveRequestTemplate";
    
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            leaveRequest: {
                name: '',
                holiday_status_id: '',
                employee_id: '',
                date_from: '',
                date_to: '',
                number_of_days_display: 0
            },
            errors: {},
            leaveTypes: [],
            employees: [],
            isSubmitting: false
        });
        
        onMounted(() => {
            this.loadData();
        });
    }

    async loadData() {
        try {
            // Cargar tipos de ausencia
            const leaveTypes = await this.rpc("/get_leave_types");
            this.state.leaveTypes = leaveTypes || [];
            
            // Cargar empleados
            const employees = await this.rpc("/get_employees");
            this.state.employees = employees || [];
            
            // Establecer empleado actual
            const currentEmployee = await this.rpc("/get_user");
            if (currentEmployee) {
                this.state.leaveRequest.employee_id = currentEmployee;
            }
        } catch (error) {
            console.error("Error loading data:", error);
        }
    }

    onDateFromChange(ev) {
        this.state.leaveRequest.date_from = ev.target.value;
        this.calculateDays();
    }

    onDateToChange(ev) {
        this.state.leaveRequest.date_to = ev.target.value;
        this.calculateDays();
    }

    onLeaveTypeChange(ev) {
        this.state.leaveRequest.holiday_status_id = ev.target.value;
        this.generateName();
    }

    calculateDays() {
        const dateFrom = new Date(this.state.leaveRequest.date_from);
        const dateTo = new Date(this.state.leaveRequest.date_to);
        
        if (dateFrom && dateTo && dateTo >= dateFrom) {
            const timeDiff = dateTo.getTime() - dateFrom.getTime();
            const daysDiff = Math.ceil(timeDiff / (1000 * 3600 * 24)) + 1; // +1 para incluir ambos días
            this.state.leaveRequest.number_of_days_display = daysDiff;
        } else {
            this.state.leaveRequest.number_of_days_display = 0;
        }
    }

    generateName() {
        if (this.state.leaveRequest.holiday_status_id && this.state.leaveRequest.date_from) {
            const leaveType = this.state.leaveTypes.find(lt => lt.id == this.state.leaveRequest.holiday_status_id);
            const dateFrom = new Date(this.state.leaveRequest.date_from).toLocaleDateString();
            this.state.leaveRequest.name = `${leaveType?.name || 'Ausencia'} - ${dateFrom}`;
        }
    }

    validateForm() {
        const errors = {};
        
        if (!this.state.leaveRequest.holiday_status_id) {
            errors.holiday_status_id = "Debe seleccionar un tipo de ausencia";
        }
        
        if (!this.state.leaveRequest.employee_id) {
            errors.employee_id = "Debe seleccionar un empleado";
        }
        
        if (!this.state.leaveRequest.date_from) {
            errors.date_from = "Debe seleccionar la fecha de inicio";
        }
        
        if (!this.state.leaveRequest.date_to) {
            errors.date_to = "Debe seleccionar la fecha de fin";
        }
        
        if (this.state.leaveRequest.date_from && this.state.leaveRequest.date_to) {
            const dateFrom = new Date(this.state.leaveRequest.date_from);
            const dateTo = new Date(this.state.leaveRequest.date_to);
            
            if (dateTo < dateFrom) {
                errors.date_to = "La fecha de fin debe ser posterior a la fecha de inicio";
            }
        }
        
        if (this.state.leaveRequest.number_of_days_display <= 0) {
            errors.number_of_days = "El número de días debe ser mayor a 0";
        }
        
        this.state.errors = errors;
        return Object.keys(errors).length === 0;
    }

    async onSubmit(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        
        if (!this.validateForm()) {
            return;
        }
        
        this.state.isSubmitting = true;
        
        try {
            await this.rpc("/safe_hr_leave", {
                leave: this.state.leaveRequest
            });
            
            window.location.href = '/leave/answer_form';
        } catch (error) {
            console.error("Error submitting leave request:", error);
            this.state.isSubmitting = false;
        }
    }

    clearForm() {
        this.state.leaveRequest = {
            name: '',
            holiday_status_id: '',
            employee_id: this.state.leaveRequest.employee_id, // Mantener empleado actual
            date_from: '',
            date_to: '',
            number_of_days_display: 0
        };
        this.state.errors = {};
    }
}
