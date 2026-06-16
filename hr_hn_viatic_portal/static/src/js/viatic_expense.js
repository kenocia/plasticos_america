/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ViaticForm = publicWidget.Widget.extend({
    selector: '.viatic_expense_form_js_class',
    events: {
        'click #add_viatic_exp': '_onClickAddExpense',
        'click #send_form': '_onSubmitForm',
        'change input': '_check_and_save_value',
        'change textarea': '_check_and_save_value',
        'change select': '_check_select_and_save_value',
        'click .delete-button': '_remove_from_list',
    },

    /**
     * @constructor
     */
    init: function (parent, options) {
        console.log("entro aqui")
        this.options = {};
        this._super.apply(this, arguments);
        this.rpc = this.bindService("rpc");
        this.orm = this.bindService("orm");
//        data form values
        this.nombre = "";
        this.place = "";
        this.date_travel="";
        this.viaje_a = "";
        this.motivo_viaje = "";
        this.fecha_desde = "";
        this.fecha_hasta = "";
        this.employee_id = "";
        this.employees_ids = [];
        this.expenses_ids = [];
        this.product_id = [];
        this.detalle = "";
        this.tarifa_aprobada = 0;
        this.cantidad_personas = 0;
        this.dias = 0;
        this.error_expense = false;
        this.error_general = false;
    },

    /**
     * Inicialización al montar el widget
     */
    start: function () {
        this._super.apply(this, arguments);
        this._loademployees();
    },

    async _loademployees() {
        const employees_ids = await this.rpc("/hr_expense/get_employees");
        const user_id = await this.rpc("/hr_expense/get_user");
        const products_ids = await this.rpc("/hr_expense/get_products");
    
        this.users = user_id;
        this.employees = employees_ids;
        this.products = products_ids;
    
        // Configurar select2 para empleados participantes
        this.$el.find('#employees_ids').select2({
            placeholder: 'Seleccione un empleado',
            data: employees_ids.map(function(item) {
                return { id: item.id, text: item.name }; // Ajustar estructura para select2
            }),
            allowClear: true,
            multiple: true,
        });

        // Configurar select2 para productos

        const $productsSelect = this.$el.find('#product_id');
        $productsSelect.empty(); // Elimina todas las opciones existentes
    
        // Agregar un placeholder vacío manualmente para asegurar que esté limpio
        $productsSelect.append(new Option('', '', true, true));
    
        // Agregar opciones dinámicamente al select
        products_ids.forEach(function(item) {
            $productsSelect.append(new Option(item.name, item.id, false, false));
        });
    
        // Inicializar Select2 con el placeholder y la capacidad de limpiar
        $productsSelect.select2({
            placeholder: 'Seleccione un producto', // Placeholder visible
            allowClear: true,                     // Permite limpiar la selección
        });
    
        // Opcional: Imprimir en consola los productos cargados
        console.log("Productos cargados:", products_ids);
        
    
        // Configurar select2 para empleado responsable
        this.$el.find('#employee_id').select2({
            placeholder: 'Seleccione un empleado',
            allowClear: true,
            data: employees_ids.map(function(item) {
                return { id: item.id, text: item.name }; // Ajustar estructura para select2
            }),
        });
    
        // Seleccionar el empleado actual como predeterminado
        if (user_id) {
            this.$el.find('#employee_id').val(user_id).trigger('change');
        }
    },
    

    _onClickAddExpense: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        this.validate_expense();
    
        if (!this.error_expense){
            this.expenses_ids.push({
                'product_id': this.product_id, // Aquí se envía el objeto completo
                'description': this.detalle,
                'approved_rate': this.tarifa_aprobada,
                'qty_person': this.cantidad_personas,
                'qty_days': this.dias,
            });
    
            // Mostrar la tabla
            var table_show = document.getElementById('viaticos_table_id');
            table_show.classList.remove("d-none");
            this._show_table();
        }
    },
    
    _onSubmitForm: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        console.log('submit form')
        this._validate_fields()
        let viatic = {
         'name': this.nombre,
         'place': this.place,
         'date': this.date_travel,
         'travel_to': this.viaje_a,
         'reason_description': this.motivo_viaje,
         'date_ini': this.fecha_desde,
         'date_end': this.fecha_hasta,
         'employee_id': this.employee_id,
         'expense_line_ids': this.expenses_ids,
        }
        console.log(viatic)
        if (this.employees_ids.length > 0 ){
            viatic.employees_ids = this.employees_ids;
        }

        if (!this.error_general){
            this.rpc("/safe_hr_viatic_expense", {
                    'viatic': viatic,

                }).then(function(result){
                    console.log("correctamente hecho todo")
                    window.location.href = '/expense/answer_form';
                })
        }

    },
    _check_and_save_value: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        this[ev.target.name] = ev.target.value;
    },
    _check_select_and_save_value: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        console.log(ev.target);
        if(ev.target.multiple) {
            const selectElement = document.getElementById('employees_ids');
            this[ev.target.name] = Array.from(selectElement.selectedOptions).map(option => option.value);
        } else {
            // Para los demás elementos, almacena su valor
            if (ev.target.name === 'product_id'){
                this[ev.target.name] = {'id': ev.target.value, 'name': ev.target.selectedOptions[0].label}
            }else{
                this[ev.target.name] = ev.target.value;
            }
        }
    },
    
    
    _validate_fields: function(){
        let  nombre = this.nombre;
        let place = this.place;
        let date_travel = this.date_travel;
        let viaje_a = this.viaje_a;
        let motivo_viaje = this.motivo_viaje;
        let fecha_desde = this.fecha_desde;
        let fecha_hasta = this.fecha_hasta;
        let employee_id = this.employee_id;
        let expenses_ids = this.expenses_ids;
        this.error_general = false;

        if (nombre == ''){
            var input_nombre = document.getElementById('input_nombre');
            input_nombre.classList.remove("d-none");
            input_nombre.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_nombre = document.getElementById('input_nombre');
            input_nombre.classList.add("d-none");
        }
        if (place == ''){
            var input_place = document.getElementById('input_place');
            input_place.classList.remove("d-none");
            input_place.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_place = document.getElementById('input_place');
            input_place.classList.add("d-none");
        }
        if (date_travel == ''){
            var input_date_travel = document.getElementById('input_date_travel');
            input_date_travel.classList.remove("d-none");
            input_date_travel.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_date_travel = document.getElementById('input_date_travel');
            input_date_travel.classList.add("d-none");
        }
        if (viaje_a == ''){
            var input_viaje_a = document.getElementById('input_viaje_a');
            input_viaje_a.classList.remove("d-none");
            input_viaje_a.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_viaje_a = document.getElementById('input_viaje_a');
            input_viaje_a.classList.add("d-none");
        }
        if (motivo_viaje == ''){
            var input_motivo_viaje = document.getElementById('input_motivo_viaje');
            input_motivo_viaje.classList.remove("d-none");
            input_motivo_viaje.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_motivo_viaje = document.getElementById('input_motivo_viaje');
            input_motivo_viaje.classList.add("d-none");
        }
        if (fecha_desde == ''){
            var input_fecha_desde = document.getElementById('input_fecha_desde');
            input_fecha_desde.classList.remove("d-none");
            input_fecha_desde.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_fecha_desde = document.getElementById('input_fecha_desde');
            input_fecha_desde.classList.add("d-none");
        }
        if (fecha_hasta == ''){
            var input_fecha_hasta = document.getElementById('input_fecha_hasta');
            input_fecha_hasta.classList.remove("d-none");
            input_fecha_hasta.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_fecha_hasta = document.getElementById('input_fecha_hasta');
            input_fecha_hasta.classList.add("d-none");
        }
        if (employee_id == ''){
            var input_employee_id = document.getElementById('input_employee_id');
            input_employee_id.classList.remove("d-none");
            input_employee_id.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_general = true;
        }else{
            var input_employee_id = document.getElementById('input_employee_id');
            input_employee_id.classList.add("d-none");
        }
        if (expenses_ids.length == 0){
            var input_expenses_ids = document.getElementById('input_expenses_ids');
            input_expenses_ids.classList.remove("d-none");
            input_expenses_ids.innerHTML = "<small class='text-danger'>Debe agregar los gastos a la solicitud de viaje</small>";
            this.error_general = true;
        }else{
            var input_expenses_ids = document.getElementById('input_expenses_ids');
            input_expenses_ids.classList.add("d-none");
        }

    },
    validate_expense: function(){
        console.log("validate")
        let product_id = this.product_id;
        let detalle = this.detalle;
        let tarifa_aprobada = this.tarifa_aprobada;
        let cantidad_personas = this.cantidad_personas;
        let dias = this.dias;
        this.error_expense = false;
        if (product_id == ''){
            var input_product_id = document.getElementById('input_product_id');
            input_product_id.classList.remove("d-none");
            input_product_id.innerHTML = "<small class='text-danger'>Debe seleccionar uno de los valores de este campo</small>";
            this.error_expense = true;
        }else{
            var input_product_id = document.getElementById('input_product_id');
            input_product_id.classList.add("d-none");
        }
        if (detalle == ''){
            var input_detalle = document.getElementById('input_detalle');
            input_detalle.classList.remove("d-none");
            input_detalle.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_expense = true;
        }else{
            var input_detalle = document.getElementById('input_detalle');
            input_detalle.classList.add("d-none");
        }
       if (tarifa_aprobada == 0){
            var input_tarifa_aprobada = document.getElementById('input_tarifa_aprobada');
            input_tarifa_aprobada.classList.remove("d-none");
            input_tarifa_aprobada.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_expense = true;
        }else{
            var input_tarifa_aprobada = document.getElementById('input_tarifa_aprobada');
            input_tarifa_aprobada.classList.add("d-none");
        }
        if (cantidad_personas == 0){
            var input_cantidad_personas = document.getElementById('input_cantidad_personas');
            input_cantidad_personas.classList.remove("d-none");
            input_cantidad_personas.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_expense = true;
        }else{
            var input_cantidad_personas = document.getElementById('input_cantidad_personas');
            input_cantidad_personas.classList.add("d-none");
        }
        if (dias == 0){
            var input_dias = document.getElementById('input_dias');
            input_dias.classList.remove("d-none");
            input_dias.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            this.error_expense = true;
        }else{
            var input_dias = document.getElementById('input_dias');
            input_dias.classList.add("d-none");
        }
        if(!this.error_expense){
         var input_expenses_ids = document.getElementById('input_expenses_ids');
            input_expenses_ids.classList.add("d-none");
        }
    },
    _show_table: function(){
        var table = document.getElementById('body_expense_viatic');
    
        while (table.rows.length > 0) {
            table.deleteRow(0);
        }
    
        let cont = 0;
        this.expenses_ids.forEach(function(exp) {
            var newRow = table.insertRow();
    
            var cell1 = newRow.insertCell(0);
            var cell2 = newRow.insertCell(1);
            var cell3 = newRow.insertCell(2);
            var cell4 = newRow.insertCell(3);
            var cell5 = newRow.insertCell(4);
            var cell6 = newRow.insertCell(5);
            var cell7 = newRow.insertCell(6);
    
            // Acceder a las propiedades de product_id
            cell1.innerHTML = exp.product_id.name || 'N/A'; // Código del producto
            cell2.innerHTML = exp.description || '';               // Descripción
            cell3.innerHTML = exp.approved_rate || 0;              // Tarifa aprobada
            cell4.innerHTML = exp.qty_person || 0;                 // Cantidad de personas
            cell5.innerHTML = exp.qty_days || 0;                   // Días
            cell6.innerHTML = (exp.qty_days * exp.qty_person * exp.approved_rate).toFixed(2) || 0; // Total
            cell7.innerHTML = `<button id="${cont}" class="round-button delete-button">
                                  <i class="fa fa-trash"></i>
                               </button>`;
            cont++;
        });
    },
    
    
    _remove_from_list: function(ev){
        ev.preventDefault()
        ev.stopPropagation();
        const id = ev.target.id
        this.expenses_ids.splice(id, 1);
        console.log(this.expenses_ids)

        this._show_table();
    },
    });