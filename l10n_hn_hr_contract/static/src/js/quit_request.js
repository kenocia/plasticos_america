/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.QuitRequestForm = publicWidget.Widget.extend({
    selector: '.quit_request_form_js_class',
    events: {
        'click #add_quit_request': '_onSubmitForm',
        'change input': '_check_and_save_value',
        'change textarea': '_check_and_save_value',
        'change select': '_check_select_and_save_value',
        'click .delete-button': '_remove_from_list',
    },

    /**
     * @constructor
     */
    init: function (parent, options) {
        console.log("entró aqui")
        this.options = {};
        this._super.apply(this, arguments);
        this.rpc = this.bindService("rpc");
        this.orm = this.bindService("orm");
//      data form values
//       Inicializar 'quit_date' con la fecha actual
        var currentDate = new Date();
        var day = ("0" + currentDate.getDate()).slice(-2);
        var month = ("0" + (currentDate.getMonth() + 1)).slice(-2);
        var year = currentDate.getFullYear();

        this.quit_date = year + "-" + month + "-" + day;
        this.penalty_to_be_applied = 0;
        this.error_quit_request = false;
        this.error_general = false;
    },
    _onSubmitForm: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        console.log('submit form')
        this._validate_fields()
        // Coger el valor al campo input en la vista
        var inputExpectedDate = document.getElementById("expected_date");
        var inputEmployeeId = document.getElementById("employee_id");

        let quit_request = {
         'quit_date': this.quit_date,
         'expected_date': inputExpectedDate.value,
         'employee_id': inputEmployeeId.value,
        }

        if (!this.error_general){
            this.rpc("/safe_hr_quit", {
                    'quit_request': quit_request,

                }).then(function(result){
                    console.log("correctamente hecho todo")
                    window.location.href = '/quit/answer_form';
                })
        }

    },
    _check_and_save_value: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        this[ev.target.name] = ev.target.value;
    },
    _validate_fields: function(){
        let quit_date = this.quit_date;
        let expected_date = this.expected_date;
        let employee_id = this.employee_id;
        this.error_general = false;

        if (quit_date  == ''){
            var input_quit_date = document.getElementById('input_quit_date');
            input_quit_date.classList.remove("d-none");
            input_quit_date.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_quit_date = document.getElementById('input_quit_date');
            input_quit_date.classList.add("d-none");
        };
        if (expected_date == ''){
            var input_expected_date = document.getElementById('input_expected_date');
            input_expected_date.classList.remove("d-none");
            input_expected_date.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_expected_date = document.getElementById('input_expected_date');
            input_expected_date.classList.add("d-none");
        }
    },
    validate_quit_request: function(){
        console.log("validate")
        let employee_id = this.employee_id;
        let quit_date = this.quit_date;

        this.error_quit_request = false;
        if (employee_id == ''){
            var input_employee_id = document.getElementById('employee_id');
            input_employee_id.classList.remove("d-none");
            input_employee_id.innerHTML = "<small class='text-danger'>Debe definir el empleado</small>";
            this.error_quit_request = true;
        }else{
            var input_employee_id = document.getElementById('employee_id');
            input_employee_id.classList.add("d-none");
        }
    },

    });
