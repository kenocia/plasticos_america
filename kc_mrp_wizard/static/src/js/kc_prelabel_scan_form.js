/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

const FOCUS_AFTER_BUTTONS = new Set(["action_add_scan"]);

/**
 * Enfoca el input de lot_barcode (handheld / escáner como teclado).
 * Mismo enfoque que kc_plasticasa kc_gs1_scan_form.js (barcode_input).
 */
export function kcFocusPrelabelBarcodeInput(rootEl) {
    if (!rootEl) {
        return false;
    }
    const selectors = [
        '.o_field_widget[name="lot_barcode"] input',
        '.o_field_widget[data-name="lot_barcode"] input',
        'div[name="lot_barcode"] input',
        '[name="lot_barcode"]',
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
    const byId = rootEl.querySelector('[id^="lot_barcode_"]');
    if (byId && typeof byId.focus === "function") {
        byId.focus();
        if (typeof byId.select === "function") {
            byId.select();
        }
        return true;
    }
    return false;
}

export function kcGetLotBarcodeInput(rootEl) {
    if (!rootEl) {
        return null;
    }
    return (
        rootEl.querySelector('.o_field_widget[name="lot_barcode"] input') ||
        rootEl.querySelector('.o_field_widget[data-name="lot_barcode"] input') ||
        rootEl.querySelector('div[name="lot_barcode"] input') ||
        rootEl.querySelector('[name="lot_barcode"]')
    );
}

/** Lee el código del input (el escáner suele dejar el valor solo en el DOM, no en el ORM aún). */
export function kcReadLotBarcodeRaw(rootEl) {
    const input = kcGetLotBarcodeInput(rootEl);
    return (input?.value || "").trim();
}

/** Sincroniza lot_barcode en el registro antes de action_add_scan / save. */
export async function kcCommitLotBarcodeToRecord(record, rootEl) {
    const input = kcGetLotBarcodeInput(rootEl);
    if (!input) {
        return "";
    }
    const val = input.value;
    const raw = (val || "").trim();
    if (raw) {
        await record.update({ lot_barcode: val });
    }
    return raw;
}

export function kcFocusPrelabelBarcodeInputWithRetry(rootEl, maxAttempts = 8) {
    let attempt = 0;
    const tryFocus = () => {
        if (kcFocusPrelabelBarcodeInput(rootEl) || attempt >= maxAttempts) {
            return;
        }
        attempt += 1;
        setTimeout(tryFocus, 60 * attempt);
    };
    tryFocus();
}

export class KcPrelabelScanFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => {
            kcFocusPrelabelBarcodeInputWithRetry(this.rootRef.el);
        });
    }

    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "action_add_scan") {
            await kcCommitLotBarcodeToRecord(this.model.root, this.rootRef.el);
        }
        return super.beforeExecuteActionButton(clickParams);
    }

    async afterExecuteActionButton(clickParams) {
        if (FOCUS_AFTER_BUTTONS.has(clickParams.name)) {
            setTimeout(() => kcFocusPrelabelBarcodeInputWithRetry(this.rootRef.el), 0);
            setTimeout(() => kcFocusPrelabelBarcodeInputWithRetry(this.rootRef.el), 150);
            setTimeout(() => kcFocusPrelabelBarcodeInputWithRetry(this.rootRef.el), 400);
        }
    }
}

registry.category("views").add("kc_prelabel_scan_wizard", {
    ...formView,
    Controller: KcPrelabelScanFormController,
});
