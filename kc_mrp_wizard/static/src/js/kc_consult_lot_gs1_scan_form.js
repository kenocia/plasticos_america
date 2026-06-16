/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

const FOCUS_AFTER_BUTTONS = new Set([
    "action_search_lot_gs1",
    "action_search_lot_manual",
]);

export function kcFocusConsultLotGs1Input(rootEl) {
    if (!rootEl) {
        return false;
    }
    const selectors = [
        '.o_field_widget[name="gs1_barcode_input"] input',
        '.o_field_widget[data-name="gs1_barcode_input"] input',
        'div[name="gs1_barcode_input"] input',
        '[name="gs1_barcode_input"]',
    ];
    for (const selector of selectors) {
        const el = rootEl.querySelector(selector);
        if (el && typeof el.focus === "function") {
            el.focus();
            if (typeof el.select === "function") {
                el.select();
            }
            return true;
        }
    }
    return false;
}

export function kcGetConsultLotGs1Input(rootEl) {
    if (!rootEl) {
        return null;
    }
    return (
        rootEl.querySelector('.o_field_widget[name="gs1_barcode_input"] input') ||
        rootEl.querySelector('.o_field_widget[data-name="gs1_barcode_input"] input') ||
        rootEl.querySelector('div[name="gs1_barcode_input"] input') ||
        rootEl.querySelector('[name="gs1_barcode_input"]')
    );
}

export async function kcCommitGs1BarcodeToRecord(record, rootEl) {
    const input = kcGetConsultLotGs1Input(rootEl);
    if (!input) {
        return "";
    }
    const val = input.value;
    const raw = (val || "").trim();
    if (raw) {
        await record.update({ gs1_barcode_input: val });
    }
    return raw;
}

export function kcFocusConsultLotGs1InputWithRetry(rootEl, maxAttempts = 8) {
    let attempt = 0;
    const tryFocus = () => {
        if (kcFocusConsultLotGs1Input(rootEl) || attempt >= maxAttempts) {
            return;
        }
        attempt += 1;
        setTimeout(tryFocus, 60 * attempt);
    };
    tryFocus();
}

export class KcConsultLotGs1ScanFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            kcFocusConsultLotGs1InputWithRetry(this.rootRef.el);
        });
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_search_lot_gs1") {
            await kcCommitGs1BarcodeToRecord(this.model.root, this.rootRef.el);
        }
        return super.beforeExecuteActionButton(clickParams);
    }

    async afterExecuteActionButton(clickParams) {
        if (FOCUS_AFTER_BUTTONS.has(clickParams.name)) {
            setTimeout(() => kcFocusConsultLotGs1InputWithRetry(this.rootRef.el), 0);
            setTimeout(() => kcFocusConsultLotGs1InputWithRetry(this.rootRef.el), 150);
        }
    }
}

registry.category("views").add("kc_consult_lot_gs1_scan_wizard", {
    ...formView,
    Controller: KcConsultLotGs1ScanFormController,
});
