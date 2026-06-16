/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { useState } from "@odoo/owl";
publicWidget.registry.ExpenseCustomList = publicWidget.Widget.extend({
    selector: '.list_js_expense_class',
    events: {
        'click input[name=checkbox_expense]': '_verify_and_select',
        'click #create_info_expense': '_create_info_expense',

    },

    init() {
        this._super(...arguments);
        this.list_to_create_info = [];
        this.rpc = this.bindService("rpc");
    },
    _verify_and_select: function (ev) {
        const isChecked = ev.target.checked;
        const inputId = ev.target.id;
        const idList = inputId.split('_')[1];
        if (isChecked) {
            this.list_to_create_info.push(idList);
        } else {
            const index = this.list_to_create_info.indexOf(idList);
            if (index > -1) {
                this.list_to_create_info.splice(index, 1);
            }
        }
        var button_info = document.getElementById('create_info_expense')
        if (this.list_to_create_info.length > 0) {
            button_info.classList.remove("d-none")
        } else {
            button_info.classList.add("d-none")
        }

    },
    _create_info_expense: async function(ev){
        ev.preventDefault()
        ev.stopPropagation();
        const expense = await this.rpc("/create_expense_sheet", {
                    expense_ids: this.list_to_create_info,
        });
        if (expense){
            window.location = '/my/expense/list';
        }

    },
});
