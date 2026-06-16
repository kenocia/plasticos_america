/** @odoo-module **/

import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";

import { Component, onWillStart } from "@odoo/owl";

class BirthdayDashboardComponent extends Component {
    setup() {
        this.orm = useService('orm');
        onWillStart(async () => {
            this.dashboardData = await this.orm.call('hr.employee', 'get_employees_of_months', []);
            console.log(this.dashboardData)
        });
    }

}

BirthdayDashboardComponent.template = 'l10n_hn_hr.Dashboard';


registry.category('actions').add('hr_birthdays_dashboard', BirthdayDashboardComponent);

export default BirthdayDashboardComponent;
