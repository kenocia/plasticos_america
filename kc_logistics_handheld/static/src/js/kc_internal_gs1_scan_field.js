/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { RPCError } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { useEffect, useState } from "@odoo/owl";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { kcFocusInternalGs1BarcodeInputWithRetry } from "./kc_internal_gs1_scan_form";

const SCAN_DEBOUNCE_MS = 200;
const GS1_CONCATENATED_RE = /^240([\w./-]+?)10(.+?)30(\d+)$/i;

function normalizeGs1Raw(raw) {
    return (raw || "")
        .trim()
        .replace(/\\x1d/gi, "\x1d")
        .replace(/\u001d/g, "\x1d")
        .replace(/\u001e/g, "\x1d")
        .replace(/\u001f/g, "\x1d");
}

function isCompleteGs1(raw) {
    const norm = normalizeGs1Raw(raw);
    if (!norm.startsWith("240")) {
        return false;
    }
    const blocks = norm.split("\x1d").filter(Boolean);
    if (blocks.length >= 2) {
        let lotName = null;
        let qty = null;
        for (const block of blocks.slice(1)) {
            if (block.startsWith("10") && !lotName) {
                lotName = block.slice(2);
            } else if (block.startsWith("30") && qty === null) {
                const qtyStr = block.slice(2);
                if (/^\d+$/.test(qtyStr)) {
                    qty = qtyStr;
                }
            }
        }
        if (lotName && qty) {
            return true;
        }
    }
    return GS1_CONCATENATED_RE.test(norm.replace(/\x1d/g, ""));
}

/**
 * Campo de escaneo GS1 igual que kc_plasticasa (foco + kc_focus_token),
 * con procesamiento automático equivalente a pulsar "Procesar QR".
 */
export class KcInternalGs1BarcodeScanField extends CharField {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.processing = useState({ value: false });
        this._debounceTimer = null;
        this._lastProcessedBarcode = null;
        this._lastProcessedAt = 0;

        useEffect(
            () => {
                const root = this.input?.el?.closest(".o_form_view") || document;
                kcFocusInternalGs1BarcodeInputWithRetry(root);
            },
            () => [this.props.record.data.kc_focus_token]
        );

        useEffect(
            (input) => {
                if (!input) {
                    return;
                }
                const onKeydown = async (ev) => {
                    if (this.processing.value) {
                        return;
                    }
                    if (ev.key === "Enter" || ev.key === "Tab") {
                        if (ev.isComposing) {
                            return;
                        }
                        ev.preventDefault();
                        ev.stopPropagation();
                        clearTimeout(this._debounceTimer);
                        await this._autoProcessQr(input, true);
                    }
                };
                const onInput = () => {
                    if (this.processing.value) {
                        return;
                    }
                    clearTimeout(this._debounceTimer);
                    this._debounceTimer = setTimeout(async () => {
                        const value = (input.value || "").trim();
                        if (isCompleteGs1(value)) {
                            await this._autoProcessQr(input, false);
                        } else if (value.length > 12) {
                            this._notifyScanResult(
                                _t("QR inválido o incompleto. Vuelva a escanear."),
                                "warning"
                            );
                            this._clearScanInput(input, this.props.record);
                        }
                    }, SCAN_DEBOUNCE_MS);
                };
                input.addEventListener("keydown", onKeydown);
                input.addEventListener("input", onInput);
                return () => {
                    clearTimeout(this._debounceTimer);
                    input.removeEventListener("keydown", onKeydown);
                    input.removeEventListener("input", onInput);
                };
            },
            () => [this.input?.el]
        );
    }

    _extractErrorMessage(error) {
        if (error instanceof RPCError) {
            return error.data?.message || error.message;
        }
        return error?.message || String(error);
    }

    _notifyScanResult(message, alertType = "info") {
        if (!message) {
            return;
        }
        const notificationType =
            alertType === "danger"
                ? "danger"
                : alertType === "success"
                  ? "success"
                  : alertType === "warning"
                    ? "warning"
                    : "info";
        this.notification.add(message, {
            type: notificationType,
            sticky: notificationType === "danger" || notificationType === "warning",
            title:
                notificationType === "danger"
                    ? _t("Error de escaneo")
                    : notificationType === "success"
                      ? _t("Escaneo correcto")
                      : _t("Aviso de escaneo"),
        });
    }

    _clearScanInput(inputEl, record) {
        if (inputEl) {
            inputEl.value = "";
        }
        if (record) {
            record.data.barcode_input = false;
        }
    }

    async _autoProcessQr(inputEl, fromTerminator = false) {
        if (this.processing.value) {
            return;
        }
        const record = this.props.record;
        if (record.data.state === "done") {
            return;
        }
        const barcode = normalizeGs1Raw(inputEl?.value || record.data.barcode_input || "");
        if (!barcode) {
            return;
        }
        if (!record.data.picking_type_id) {
            this._notifyScanResult(
                _t("Debe seleccionar un tipo de operación interna."),
                "warning"
            );
            return;
        }
        if (!isCompleteGs1(barcode)) {
            if (fromTerminator || barcode.length > 12) {
                this._notifyScanResult(
                    _t("QR inválido. No se encontraron producto, lote y cantidad."),
                    "warning"
                );
                this._clearScanInput(inputEl, record);
            }
            return;
        }

        const now = Date.now();
        if (
            barcode === this._lastProcessedBarcode &&
            now - this._lastProcessedAt < 2500
        ) {
            this._clearScanInput(inputEl, record);
            return;
        }

        this.processing.value = true;
        this._lastProcessedBarcode = barcode;
        this._lastProcessedAt = now;
        clearTimeout(this._debounceTimer);

        try {
            await record.update({ barcode_input: barcode });
            await record.model.root.save();
            await this.actionService.doActionButton({
                type: "object",
                name: "action_process_qr",
                resModel: record.resModel,
                resId: record.resId,
                resIds: [record.resId],
                context: record.context,
            });
            await record.model.root.load();
            this._notifyScanResult(record.data.message, record.data.scan_alert_type);
            this._lastProcessedBarcode = null;
            this._lastProcessedAt = 0;
        } catch (error) {
            this._lastProcessedBarcode = null;
            this._lastProcessedAt = 0;
            this._notifyScanResult(this._extractErrorMessage(error), "danger");
        } finally {
            this.processing.value = false;
            this._clearScanInput(inputEl, record);
            const root = this.input?.el?.closest(".o_form_view") || document;
            kcFocusInternalGs1BarcodeInputWithRetry(root);
        }
    }
}

export const kcInternalGs1BarcodeScanField = {
    ...charField,
    component: KcInternalGs1BarcodeScanField,
};

registry.category("fields").add("kc_internal_gs1_barcode_scan", kcInternalGs1BarcodeScanField);
