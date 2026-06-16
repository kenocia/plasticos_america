/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

const FOCUS_BUTTONS = new Set([
    "action_process_qr",
    "action_create_and_validate_transfer",
]);

/**
 * Enfoca el input del campo barcode_input dentro del wizard (modal).
 * Misma lógica que kc_plasticasa/static/src/js/kc_gs1_scan_form.js
 */
export function kcFocusInternalGs1BarcodeInput(rootEl) {
    if (!rootEl) {
        return false;
    }
    const selectors = [
        '.o_field_widget[name="barcode_input"] input',
        '.o_field_widget[data-name="barcode_input"] input',
        'div[name="barcode_input"] input',
        '[name="barcode_input"]',
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
    const byId = rootEl.querySelector('[id^="barcode_input_"]');
    if (byId && typeof byId.focus === "function") {
        byId.focus();
        if (typeof byId.select === "function") {
            byId.select();
        }
        return true;
    }
    return false;
}

export function kcFocusInternalGs1BarcodeInputWithRetry(rootEl, maxAttempts = 8) {
    let attempt = 0;
    const tryFocus = () => {
        if (kcFocusInternalGs1BarcodeInput(rootEl) || attempt >= maxAttempts) {
            return;
        }
        attempt += 1;
        setTimeout(tryFocus, 60 * attempt);
    };
    tryFocus();
}

export class KcInternalGs1ScanFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            kcFocusInternalGs1BarcodeInputWithRetry(this.rootRef.el);
        });
    }

    async afterExecuteActionButton(clickParams) {
        await super.afterExecuteActionButton?.(clickParams);
        if (FOCUS_BUTTONS.has(clickParams.name)) {
            setTimeout(() => kcFocusInternalGs1BarcodeInputWithRetry(this.rootRef.el), 0);
            setTimeout(() => kcFocusInternalGs1BarcodeInputWithRetry(this.rootRef.el), 150);
            setTimeout(() => kcFocusInternalGs1BarcodeInputWithRetry(this.rootRef.el), 400);
        }
    }
}

registry.category("views").add("kc_internal_gs1_scan_wizard", {
    ...formView,
    Controller: KcInternalGs1ScanFormController,
});
