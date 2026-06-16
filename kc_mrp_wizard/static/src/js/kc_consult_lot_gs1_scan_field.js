/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useEffect } from "@odoo/owl";
import { CharField, charField } from "@web/views/fields/char/char_field";
import {
    kcFocusConsultLotGs1InputWithRetry,
} from "./kc_consult_lot_gs1_scan_form";

/**
 * Campo GS1 del wizard «Consultar lote»: Enter ejecuta action_search_lot_gs1.
 */
export class KcConsultLotGs1ScanField extends CharField {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this._kcEnterBusy = false;

        useEffect(
            () => {
                const root = this.input?.el?.closest(".o_form_view") || document;
                kcFocusConsultLotGs1InputWithRetry(root);
            },
            () => [this.props.record.data.kc_focus_token]
        );

        useEffect(
            (inputEl) => {
                if (!inputEl) {
                    return;
                }
                const onKeydown = async (ev) => {
                    if (ev.key !== "Enter" || this.props.readonly || this._kcEnterBusy) {
                        return;
                    }
                    const raw = (inputEl.value || "").trim();
                    if (!raw) {
                        return;
                    }
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();
                    this._kcEnterBusy = true;
                    try {
                        const record = this.props.record;
                        await record.update({ gs1_barcode_input: raw });
                        await record.model.root.save();
                        await this.actionService.doActionButton({
                            name: "action_search_lot_gs1",
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
                    }
                };
                inputEl.addEventListener("keydown", onKeydown, true);
                return () => inputEl.removeEventListener("keydown", onKeydown, true);
            },
            () => [this.input.el]
        );
    }
}

export const kcConsultLotGs1ScanField = {
    ...charField,
    component: KcConsultLotGs1ScanField,
};

registry.category("fields").add("kc_consult_lot_gs1_scan", kcConsultLotGs1ScanField);
