/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

const FOCUS_BUTTONS = new Set([
    "action_apply_scan",
    "action_process_qr",
    "action_on_barcode_scanned",
    "action_clear_ramp",
    "action_new_ramp",
]);

/**
 * Enfoca el input del campo barcode_input dentro del wizard (modal).
 */
export function kcFocusGs1BarcodeInput(rootEl) {
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

export function kcGetGs1BarcodeInput(rootEl) {
    if (!rootEl) {
        return null;
    }
    return (
        rootEl.querySelector('.o_field_widget[name="barcode_input"] input') ||
        rootEl.querySelector('.o_field_widget[data-name="barcode_input"] input') ||
        rootEl.querySelector('div[name="barcode_input"] input') ||
        rootEl.querySelector('[name="barcode_input"]')
    );
}

/** Sincroniza barcode_input en el registro antes de la acción del servidor. */
export async function kcCommitGs1BarcodeToRecord(record, rootEl) {
    const input = kcGetGs1BarcodeInput(rootEl);
    if (!input) {
        return "";
    }
    const val = input.value;
    const raw = (val || "").trim();
    if (raw) {
        await record.update({ barcode_input: val });
    }
    return raw;
}

export function kcFocusGs1BarcodeInputWithRetry(rootEl, maxAttempts = 8) {
    let attempt = 0;
    const tryFocus = () => {
        if (kcFocusGs1BarcodeInput(rootEl) || attempt >= maxAttempts) {
            return;
        }
        attempt += 1;
        setTimeout(tryFocus, 60 * attempt);
    };
    tryFocus();
}

export class KcGs1ScanFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            kcFocusGs1BarcodeInputWithRetry(this.rootRef.el);
        });
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_on_barcode_scanned") {
            await kcCommitGs1BarcodeToRecord(this.model.root, this.rootRef.el);
        }
        return super.beforeExecuteActionButton(clickParams);
    }

    async afterExecuteActionButton(clickParams) {
        await super.afterExecuteActionButton(clickParams);
        if (FOCUS_BUTTONS.has(clickParams.name)) {
            setTimeout(() => kcFocusGs1BarcodeInputWithRetry(this.rootRef.el), 0);
            setTimeout(() => kcFocusGs1BarcodeInputWithRetry(this.rootRef.el), 150);
            setTimeout(() => kcFocusGs1BarcodeInputWithRetry(this.rootRef.el), 400);
        }
    }
}

registry.category("views").add("kc_gs1_scan_wizard", {
    ...formView,
    Controller: KcGs1ScanFormController,
});
