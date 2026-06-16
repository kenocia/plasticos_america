/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEffect } from "@odoo/owl";
import { CharField, charField } from "@web/views/fields/char/char_field";
import {
    kcCommitLotBarcodeToRecord,
    kcFocusPrelabelBarcodeInputWithRetry,
} from "./kc_prelabel_scan_form";

/**
 * Campo de escaneo pre-etiqueta:
 * - Refuerza el foco cuando cambia kc_focus_token.
 * - Enter del handheld ejecuta «Añadir a la lista» (action_add_scan).
 */
export class KcPrelabelBarcodeScanField extends CharField {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this._kcEnterBusy = false;

        useEffect(
            () => {
                const root = this.input?.el?.closest(".o_form_view") || document;
                kcFocusPrelabelBarcodeInputWithRetry(root);
            },
            () => [this.props.record.data.kc_focus_token]
        );

        useEffect(
            (inputEl) => {
                if (!inputEl) {
                    return;
                }
                const onKeydown = (ev) => this._onLotBarcodeKeydown(ev);
                // capture: antes que useInputField, para commitear y lanzar la acción
                inputEl.addEventListener("keydown", onKeydown, true);
                return () => inputEl.removeEventListener("keydown", onKeydown, true);
            },
            () => [this.input.el]
        );
    }

    async _onLotBarcodeKeydown(ev) {
        if (ev.key !== "Enter") {
            return;
        }

        const input = this.input.el;
        if (!input || this.props.readonly || this._kcEnterBusy) {
            return;
        }

        const root = input.closest(".o_form_view");
        const raw = (input.value || "").trim();
        if (!raw) {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();

        this._kcEnterBusy = true;
        try {
            const record = this.props.record;
            await kcCommitLotBarcodeToRecord(record, root);

            await this.actionService.doActionButton({
                name: "action_add_scan",
                type: "object",
                resModel: record.resModel,
                resId: record.resId,
                resIds: record.resIds?.length ? record.resIds : [record.resId],
                context: {
                    ...record.context,
                    kc_lot_barcode_scan: raw,
                },
            });
        } finally {
            this._kcEnterBusy = false;
        }
    }
}

export const kcPrelabelBarcodeScanField = {
    ...charField,
    component: KcPrelabelBarcodeScanField,
};

registry.category("fields").add("kc_prelabel_barcode_scan", kcPrelabelBarcodeScanField);
