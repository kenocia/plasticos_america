/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { useState } from "@odoo/owl";
publicWidget.registry.PositionCustomList = publicWidget.Widget.extend({
    selector: '.list_js_position_class',
    events: {
        'click #first_pos': '_create_info_expense',
        'click #custom_position_id': '_safe_value_position',
        'change #selection_pos_id': '_onchange_save',
        'change #qty_id': '_onchange_save_qty',

    },

    init() {
        this._super(...arguments);
        this.list_to_create_info = [];
        this.rpc = this.bindService("rpc");
        this.selectionValue = '';
        this.qty = 1;
    },
    _onchange_save_qty: function (ev) {
        this.qty = ev.target.value
        console.log(this.qty)
    },
    _onchange_save: function (ev) {

        this.selectionValue = ev.target.value
        console.log(this.selectionValue)
    },

    _safe_value_position: function (ev) {
        ev.preventDefault()
        ev.stopPropagation();
        console.log(this.selectionValue)
        let selectedValue = this.selectionValue
        let qty = this.qty
        if (this.selectionValue == '' || this.selectionValue == '0'){
        var text = document.getElementById('text_error_id')
            text.classList.remove("d-none")
        }else{
         this.rpc("/create_request_position_hr", {
                    'hr_position_id': selectedValue,
                    'qty': this.qty,
                }).then(function(result){
                    console.log("correctamente hecho todo")
                    window.location.href = '/request/position/list';
                })
}
    },
    _create_info_expense: async function(ev){
        ev.preventDefault()
        ev.stopPropagation();
        console.log("Click")
        var button_info = document.getElementById('custom_position_id')
        var qty_id = document.getElementById('qty_id')
        var first_pos = document.getElementById('first_pos')
        first_pos.classList.add("d-none")
        button_info.classList.remove("d-none")
        var selection = document.getElementById('selection_pos_id')
        selection.classList.remove("d-none")
        qty_id.classList.remove("d-none")
    },
});
