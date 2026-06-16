/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { useState } from "@odoo/owl";
console.log('expense')
publicWidget.registry.ExpenseCustom = publicWidget.Widget.extend({
    selector: '.expense_form_js_class',

    events: {
        'click #product_id': '_openLink',
        'click .save_and_new': '_saveAndNew',
        'change #product_id': '_get_quantity',
        'change #quantity': '_get_amount_total',
        'click .save_all': '_save_all',
        'click .delete-button': '_remove_from_list',
    },
    init() {
        this._super(...arguments);
        this.expense_list = [];
        this.rpc = this.bindService("rpc");
        this.is_multiple = false;
        this.error = false;
        this.show_quantity = false;
        this.unit_price = 0;
    },


    _openLink: function (ev) {
        console.log(ev.target.value)
        let product_id = ev.target.value
        console.log('click en un componente de select')
    },
    _validate: function(expense){
        this.error = false
//        validate name
        if (expense['name'] === ''){
            var input_name = document.getElementById('input_name');
            input_name.classList.remove("d-none");
            input_name.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>"
            this.error = true
        }else{
            var input_name = document.getElementById('input_name');
            input_name.classList.add("d-none");
        }
//        validate description
        if (expense['description']  === ''){
            var input_description = document.getElementById('input_description');
            input_description.classList.remove("d-none");
            input_description.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error = true
        }else{
            var input_description = document.getElementById('input_description');
            input_description.classList.add("d-none");
        }
//        validate date
        if (expense['date']  === ''){
            var input_date = document.getElementById('input_date');
            input_date.classList.remove("d-none");
            input_date.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error = true
        }

       
//        validate payment mode
        if (expense['payment_mode']  === undefined){
            var input_payment_mode = document.getElementById('input_payment_mode');
            input_payment_mode.classList.remove("d-none");
            input_payment_mode.innerHTML = "<small class='text-danger'>Debe seleccionar uno de los valores de este campo</small>";
            this.error = true
        }else{
            var input_payment_mode = document.getElementById('input_payment_mode');
            input_payment_mode.classList.add("d-none");
        }
//        validate quanatity
        if (this.show_quantity && expense['quantity']  === ''){
            var input_quantity = document.getElementById('input_quantity');
            input_quantity.classList.remove("d-none");
            input_quantity.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error = true
        }else{
            var input_quantity = document.getElementById('input_quantity');
            input_quantity.classList.add("d-none");
        }
//      total_amount_currency
        if (expense['total_amount_currency']  === ''){
            var input_amount_currency = document.getElementById('input_amount_currency');
            input_amount_currency.classList.remove("d-none");
            input_amount_currency.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error = true
        }else{
            var input_amount_currency = document.getElementById('input_amount_currency');
            input_amount_currency.classList.add("d-none");
        }

    },
    _get_quantity: async function (ev) {
        let product_id = ev.target.value
         const product = await this.rpc("/get_value_of_product", {
                    product_id: product_id,
         });
         var elemento = document.getElementById("quantity_id");
         if (product['quantity']){
            elemento.classList.remove("d-none");
            this.show_quantity = true;
            this.unit_price = product['unit_price'];
         }else{
            elemento.classList.add("d-none");
            this.show_quantity = false;
            this.unit_price = 0;
         }
        console.log('click en un componente de select')
    },
    _saveAndNew: function (ev) {
        ev.preventDefault()
        ev.stopPropagation();
        let expense = this._get_values_of_form()
        this._validate(expense);
        console.log(expense)
        if (!this.error){
            this.expense_list.push(expense)
            console.log(this.expense_list)
        }
        var table_show = document.getElementById('expense_table_show');
        table_show.classList.remove("d-none");
        this._show_table();
        this._clear_fields_inputs_form();
    },
    _save_all: async function(ev){
        ev.preventDefault()
        ev.stopPropagation();
        let expense = this._get_values_of_form()
        this._validate(expense);
        console.log(expense)
        if (!this.error){
           this.expense_list.push(expense)
           setTimeout(() => {
                console.log("timeout")
                console.log(this.expense)
                this.rpc("/safe_hr_expense", {
                    expense_list: this.expense_list,
                }).then(function(result){
                    console.log("correctamente hecho todo")
                    window.location.href = '/expense/answer_form';
                })
            }, 2000);

        }


    },
     _get_values_of_form: function(ev){
        console.log("entro al get_value_of_form")
        // Selecciona todos los elementos input, select y textarea dentro del div con la clase 'expense_form_js_class'
        var elements = document.querySelectorAll('.expense_form_js_class input, .expense_form_js_class select, .expense_form_js_class textarea');

        // Crea un objeto para almacenar los valores
        let expense = {};

        // Itera sobre los elementos y almacena sus valores en el objeto
        elements.forEach(function(element) {
            console.log(element)
            if(element.type === "radio" || element.type === "checkbox") {
                // Para los elementos de tipo radio y checkbox, almacena si están seleccionados
                console.log(element.checked)
                if (element.checked){
                    expense[element.name] = element.value;
                }
            } else if(element.type === "select-multiple") {
                // Para los elementos de tipo select-multiple, almacena un array con los valores seleccionados
                expense[element.name] = Array.from(element.selectedOptions).map(option => option.value);
            } else {
                // Para los demás elementos, almacena su valor
                expense[element.name] = element.value;
            }
        });
        // Selecciona el elemento input de tipo file
        var inputFile = document.querySelector('#archivo_adjunto');

        // Obtiene los archivos seleccionados

        var fileArray = [];

        // Añade los archivos al objeto FormData
        // Si el input permite múltiples archivos, los añade todos
        for (var i = 0; i < inputFile.files.length; i++) {
            let reader = new FileReader();
            reader.readAsDataURL(inputFile.files[i]);
            console.log(inputFile.files[i])
            var files = inputFile.files[i];
            reader.onloadend = function() {
                let base64data = reader.result;
                fileArray.push({
                    data: base64data,
                    name: files['name'],
                    type: files['type']
                });
            }
        }
        expense['archivo_adjunto'] = fileArray
        return expense;
    },

    _show_table: function(){
        // Obtener la referencia de la tabla
        var table = document.getElementById('expense_table_id');

        while (table.rows.length > 0) {
            table.deleteRow(0);
        }
        let cont = 0;
        this.expense_list.forEach(function(exp) {
            // Crear una nueva fila
            var newRow = table.insertRow();

            // Insertar celdas en la nueva fila
            var cell1 = newRow.insertCell(0);
            var cell2 = newRow.insertCell(1);
            var cell3 = newRow.insertCell(2);
            var cell4 = newRow.insertCell(3);
            var cell5 = newRow.insertCell(4);

            // Agregar valores a las celdas
            cell1.innerHTML = exp.name;
            cell2.innerHTML = exp.date;
            cell3.innerHTML = exp.total_amount_currency;
            cell4.innerHTML = exp.description;
            cell5.innerHTML = '<button id='+cont+' class="round-button delete-button"> <i class="fa fa-trash"></i>'
        });
    },
    _remove_from_list: function(ev){
        ev.preventDefault()
        ev.stopPropagation();

        const id = ev.target.id
        this.expense_list.splice(id, 1);
        console.log(this.expense_list)
        this._show_table();
    },
    _clear_fields_inputs_form: function(ev){

         var elements = document.querySelectorAll('.expense_form_js_class input, .expense_form_js_class select, .expense_form_js_class textarea');

        // Itera sobre los elementos y almacena sus valores en el objeto
        elements.forEach(function(element) {
            if(element.type === "radio" || element.type === "checkbox") {
            } else if(element.type === "select-multiple") {
                // Para los elementos de tipo select-multiple, almacena un array con los valores seleccionados
                let opciones = element.selectedOptions;
                for (let i = 0; i < opciones.length; i++) {
                    opciones[i].selected = false;
                }
            } else {
                // Para los demás elementos, almacena su valor
                element.value = "";
            }
        });
        this.error = false;
        this.show_quantity = false;
        this.unit_price = 0;
    },

    _get_amount_total: function(ev){
        ev.preventDefault();
        console.log("_get_amount_total");
        console.log(ev.target.value);
        let unit_price = this.unit_price;
        var qty = parseInt(ev.target.value);
        let total_amount_currency = unit_price * qty;
        console.log(total_amount_currency);
        var total_element = document.getElementById("total_amount_currency");
        console.log(total_element)
        total_element.value = total_amount_currency;
    },

});
