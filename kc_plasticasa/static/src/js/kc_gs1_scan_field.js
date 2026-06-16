/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEffect } from "@odoo/owl";
import { CharField, charField } from "@web/views/fields/char/char_field";
import {
    kcCommitGs1BarcodeToRecord,
    kcFocusGs1BarcodeInputWithRetry,
} from "./kc_gs1_scan_form";

/**
 * Campo de escaneo GS1:
 * - Refuerza el foco cuando cambia kc_focus_token.
 * - Enter del handheld ejecuta procesar + aplicar (action_on_barcode_scanned).
 */
export class KcGs1BarcodeScanField extends CharField {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this._kcEnterBusy = false;

        useEffect(
            () => {
                const root = this.input?.el?.closest(".o_form_view") || document;
                kcFocusGs1BarcodeInputWithRetry(root);
            },
            () => [this.props.record.data.kc_focus_token]
        );

        useEffect(
            (inputEl) => {
                if (!inputEl) {
                    return;
                }
                const onKeydown = (ev) => this._onBarcodeKeydown(ev);
                inputEl.addEventListener("keydown", onKeydown, true);
                return () => inputEl.removeEventListener("keydown", onKeydown, true);
            },
            () => [this.input.el]
        );
    }

    _clearBarcodeInput(input) {
        if (input) {
            input.value = "";
        }
        const record = this.props.record;
        if (record) {
            record.data.barcode_input = false;
        }
    }

    async _onBarcodeKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }

        const input = this.input.el;
        if (!input || this.props.readonly || this._kcEnterBusy) {
            return;
        }

        const raw = (input.value || "").trim();
        if (!raw) {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();

        this._kcEnterBusy = true;
        const root = input.closest(".o_form_view");
        try {
            const record = this.props.record;
            await kcCommitGs1BarcodeToRecord(record, root);

            // No llamar record.model.root.load(): el servidor reabre el wizard y un
            // load() extra provoca "Component is destroyed".
            await this.actionService.doActionButton({
                name: "action_on_barcode_scanned",
                type: "object",
                resModel: record.resModel,
                resId: record.resId,
                resIds: record.resIds?.length ? record.resIds : [record.resId],
                context: {
                    ...record.context,
                    kc_gs1_barcode_scan: raw,
                },
            });
        } finally {
            this._kcEnterBusy = false;
            this._clearBarcodeInput(input);
            kcFocusGs1BarcodeInputWithRetry(
                this.input?.el?.closest(".o_form_view") || document
            );
        }
    }
}

export const kcGs1BarcodeScanField = {
    ...charField,
    component: KcGs1BarcodeScanField,
};

registry.category("fields").add("kc_gs1_barcode_scan", kcGs1BarcodeScanField);
