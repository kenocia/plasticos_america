/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { useState } from "@odoo/owl";

publicWidget.registry.ExpenseCustomList = publicWidget.Widget.extend({
    selector: '.list_js_leave_class',
    events: {
        'click #add_leave': '_onSubmitForm',
        'change .date_from-leave': '_dateFromLeave',
        'change .date_to-leave': '_dateToLeave',
        'change .leave_type-leave': '_leaveTypeSelect',
    },

    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
    },
    _onSubmitForm: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        console.log('submit form')
        this._validate_fields()
        // Coger el valor al campo input en la vista
        var inputDateFrom = document.getElementById("date_from");
        var inputDateTo = document.getElementById("date_to");
        var inputEmployeeId = document.getElementById("employee_id");
        var inputStatusId = document.getElementById("leave_type_id");
        var inputNumberDayDisplay = document.getElementById("number_of_days_display");

        if (!this.error_general){
            let leave = {
                 'name': this.name,
                 'holiday_status_id': inputStatusId.value,
                 'employee_id': inputEmployeeId.value,
                 'date_from': inputDateFrom.value,
                 'date_to': inputDateTo.value,
            }

            this.rpc("/safe_hr_leave", {
                    'leave': leave,

                }).then(function(result){
                    console.log("Ausencia solicitada")
                    window.location.href = '/leave/answer_form';
                })
        }
        },
    _validate_fields: function(){
        let holiday_status_id = document.getElementById("leave_type_id");
        let date_from = this.date_from;
        let date_to = this.date_to;
        let inputDateFrom = document.getElementById("date_from");
        let inputDateTo = document.getElementById("date_to");

        var from_date_val = new Date(inputDateFrom.value);
        var to_date_val = new Date(inputDateTo.value);

        this.error_general = false;

        if (holiday_status_id.value  == ''){
            var inputHolidayStatusError= document.getElementById('input_leave_type');
            inputHolidayStatusError.classList.remove("d-none");
            inputHolidayStatusError.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        } else {
            var inputHolidayStatusError= document.getElementById('input_leave_type');
            inputHolidayStatusError.classList.add("d-none");
        };
        if (from_date_val) {
            var inputDateFromError = document.getElementById("input_date_from");
            if (to_date_val < from_date_val) {
               inputDateFromError.classList.remove("d-none");
               inputDateFromError.innerHTML = "<small class='text-danger'>Por favor la fecha de fin debe ser mayor que la fecha de inicio!</small>";
               this.error_general = true;
            } else  {
                inputDateFromError.classList.add("d-none");
            }
        } else {
           inputDateFromError.classList.remove("d-none");
           inputDateFromError.innerHTML = "<small class='text-danger'>Por favor debe especificar la fecha de fin!</small>";
           this.error_general = true;
        }
        var haveAllocationTag = document.getElementById('have_allocation');
        var haveAllocationValue = haveAllocationTag.getAttribute('data-value');
        var haveAllocation = (haveAllocationValue === 'True')
        var requiresDayTag = document.getElementById('requires_day');
        var requiresDayValue = requiresDayTag.getAttribute('data-value');
        var requiresDay = (requiresDayValue === 'True')
        if (haveAllocation) {
            // Realiza acciones si tiene asignación
            var inputAllocationValue = document.getElementById("allocation").value;
            var inputAllocationError= document.getElementById('input_allocation');
            var allocationAsInt = parseInt(inputAllocationValue, 10);
            if (allocationAsInt == 0) {
                inputAllocationError.classList.remove("d-none");
                inputAllocationError.innerHTML = "<small class='text-danger'>No se puede encontrar una asignación para el periodo de tiempo solicitado</small>";
                this.error_general = true;
            }
            var request_value = 0
            if (requiresDay)  {
                request_value = document.getElementById("days").value;
            } else {
                request_value = document.getElementById("hours").value;
            }
            var requestAsInt = parseInt(request_value, 10);
            if (allocationAsInt < requestAsInt)  {
                inputAllocationError.classList.remove("d-none");
                inputAllocationError.innerHTML = "<small class='text-danger'>El tiempo solicitado no puede ser mayor que el disponible</small>";
                this.error_general = true;
            }
            if (this.error_general == false) {
                inputAllocationError.classList.add("d-none");
            }
        }
    },
    _leaveTypeSelect: function(ev){
            var inputEmployeeId = document.getElementById("employee_id");
            var inputDateFrom = document.getElementById("date_from");
            var inputDateTo = document.getElementById("date_to");
            var inputStatusId = document.getElementById("leave_type_id");
            var input_holiday_status_id = document.getElementById('leave_type_id').value;
            var inputHolidayStatusError= document.getElementById('input_leave_type');

            var employee_id = inputEmployeeId.value
            var from_date_val = new Date(inputDateFrom.value);
            var to_date_val = new Date(inputDateTo.value);
            var leave_type_id = inputStatusId.value;

            if (input_holiday_status_id  == ''){
                inputHolidayStatusError.classList.remove("d-none");
                inputHolidayStatusError.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
                return false;
             } else {
                inputHolidayStatusError.classList.add("d-none");
             }
             this.rpc('/my/leaves/allocation', {
                     'employee_id': employee_id,
                    'leave_type_id': leave_type_id,
             }).then((data) => {
                var days = data.days;
                var requires = data.requires;
                $("#allocation").val(days);
                var _style = 'none';
                var haveAllocationTag = document.getElementById('have_allocation');
                haveAllocationTag.setAttribute('data-value', 'False');
                if (requires == 1){
                    haveAllocationTag.setAttribute('data-value', 'True');
//                    _style = 'block';
                    _style = '';
                }
                $(".allocation_div").css('display', _style)

             });

            this.rpc('/my/leaves/number_of_day', {
                    'employee_id': employee_id,
                    'date_from': from_date_val,
                    'date_to': to_date_val,
                    'leave_type_id': leave_type_id,
                }).then((data) => {
                var days = data.days;
                var requires_day = data.requires_day;
                var requires_hour = data.requires_hour;
                var _style = 'none';
                var requiresDayTag = document.getElementById('requires_day');
                requiresDayTag.setAttribute('data-value', 'False');
                if (requires_day == 1){
                    $("#days").val(days);
                    requiresDayTag.setAttribute('data-value', 'True');
//                    _style = 'block';
                    _style = '';
                    $(".days_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".days_div").css('display', _style)
                }
                if (requires_hour == 1){
                   $("#hours").val(days);
//                    _style = 'block';
                    _style = '';
                    $(".hours_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".hours_div").css('display', _style)
                }
            });

    },
    _dateFromLeave: function(ev){
            var inputEmployeeId = document.getElementById("employee_id");
            var inputDateFrom = document.getElementById("date_from");
            var inputDateTo = document.getElementById("date_to");
            var inputStatusId = document.getElementById("leave_type_id");

            var employee_id = inputEmployeeId.value
            var from_date_val = new Date(inputDateFrom.value);
            var to_date_val = new Date(inputDateTo.value);
            var leave_type_id = inputStatusId.value;

            if (leave_type_id.value  == ''){
                var inputHolidayStatusError= document.getElementById('input_leave_type');
                inputHolidayStatusError.classList.remove("d-none");
                inputHolidayStatusError.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            } else {
                var inputHolidayStatusError= document.getElementById('input_leave_type');
                inputHolidayStatusError.classList.add("d-none");
            };

            this.rpc('/my/leaves/number_of_day', {
                    'employee_id': employee_id,
                    'date_from': from_date_val,
                    'date_to': to_date_val,
                    'leave_type_id': leave_type_id,
                }).then((data) => {
                var days = data.days;
                var requires_day = data.requires_day;
                var requires_hour = data.requires_hour;
                var _style = 'none';
                var requiresDayTag = document.getElementById('requires_day');
                requiresDayTag.setAttribute('data-value', 'False');
                if (requires_day == 1){
                    $("#days").val(days);
                    requiresDayTag.setAttribute('data-value', 'True');
//                    _style = 'block';
                    _style = '';
                    $(".days_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".days_div").css('display', _style)
                }
                if (requires_hour == 1){
                   $("#hours").val(days);
//                    _style = 'block';
                    _style = '';
                    $(".hours_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".hours_div").css('display', _style)
                }
            });
            this._validate_fields()
  },
    _dateToLeave: function(ev){
            var inputEmployeeId = document.getElementById("employee_id");
            var inputDateFrom = document.getElementById("date_from");
            var inputDateTo = document.getElementById("date_to");
            var inputStatusId = document.getElementById("leave_type_id");

            var employee_id = inputEmployeeId.value
            var from_date_val = new Date(inputDateFrom.value);
            var to_date_val = new Date(inputDateTo.value);
            var leave_type_id = inputStatusId.value;

            if (leave_type_id.value  == ''){
                var inputHolidayStatusError= document.getElementById('input_leave_type');
                inputHolidayStatusError.classList.remove("d-none");
                inputHolidayStatusError.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            } else {
                var inputHolidayStatusError= document.getElementById('input_leave_type');
                inputHolidayStatusError.classList.add("d-none");
            };

            this.rpc('/my/leaves/number_of_day', {
                    'employee_id': employee_id,
                    'date_from': from_date_val,
                    'date_to': to_date_val,
                    'leave_type_id': leave_type_id,
                }).then((data) => {
                var days = data.days;
                var requires_day = data.requires_day;
                var requires_hour = data.requires_hour;
                var _style = 'none';
                var requiresDayTag = document.getElementById('requires_day');
                requiresDayTag.setAttribute('data-value', 'False');
                if (requires_day == 1){
                    $("#days").val(days);
                    requiresDayTag.setAttribute('data-value', 'True');
//                    _style = 'block';
                    _style = '';
                    $(".days_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".days_div").css('display', _style)
                }
                if (requires_hour == 1){
                   $("#hours").val(days);
//                    _style = 'block';
                    _style = '';
                    $(".hours_div").css('display', _style)
                } else {
                    _style = 'none';
                    $(".hours_div").css('display', _style)
                }
            });
            this._validate_fields()
    },
});
