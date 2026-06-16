/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { useState } from "@odoo/owl";

publicWidget.registry.NewAppList = publicWidget.Widget.extend({
    selector: '.js_list_applicant_job',

    events: {
        'click #list_button_app_id': '_openLink',
        'click input[name=checkbox_list_app]': '_verify_and_select',
    },
    init() {
        this._super(...arguments);
        this.list_to_create_info = [];
        this.rpc = this.bindService("rpc");
    },
    _openLink: async function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var job_id = document.getElementById('input_job')
        const expense = await this.rpc("/approve_candidates", {
                    app_list: this.list_to_create_info,
                    job_id: job_id.value
        });
        if (expense){
            window.location = "/candidatos/solicitudes/"+expense;
        }
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
        var button_info = document.getElementById('list_button_app_id')
        if (this.list_to_create_info.length > 0) {
            button_info.classList.remove("d-none")
        } else {
            button_info.classList.add("d-none")
        }

    },


});