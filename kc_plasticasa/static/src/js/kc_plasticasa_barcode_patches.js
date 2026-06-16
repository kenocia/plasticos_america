/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BarcodeParser } from "@barcodes/js/barcode_parser";
import { FNC1_CHAR } from "@barcodes_gs1_nomenclature/js/barcode_parser";
import BarcodeModel from "@stock_barcode/models/barcode_model";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";

/**
 * El AI (10) es longitud variable; en Odoo el separador tras (10) es opcional en el regex, así que sin FNC1
 * el grupo (10) puede crecer hasta 20 caracteres y tragarse el inicio del (30) → lote "…30140" y cantidad 1.
 * Muchos lectores de QR/cámara no devuelven el ASCII 29 entre campos.
 *
 * Debe ejecutarse también al inicio de processBarcode: el escaneo por cámara no pasa por cleanBarcode, y
 * BarcodeObject.forBarcode parsea antes de _processBarcode.
 */
function kcPreprocessPlasticasaGs1Scan(barcode, gs) {
    if (typeof barcode !== "string" || !barcode.includes("10")) {
        return barcode;
    }
    let b = barcode.replace(/^\uFEFF/, "").trim();
    if (b.normalize) {
        b = b.normalize("NFKC");
    }
    b = b.replace(/\u241D/g, gs).replace(/\u001E/g, gs).replace(/\u001F/g, gs);
    const tryInsertBefore = (regex) => {
        const m = b.match(regex);
        if (!m) {
            return false;
        }
        const before = m[1];
        if (before.endsWith(gs)) {
            return false;
        }
        if (!/10/.test(before)) {
            return false;
        }
        b = before + gs + m[2] + m[3];
        return true;
    };
    // (30) + 1..8 dígitos al final (piezas)
    if (!tryInsertBefore(/^(.*)(30)(\d{1,8})$/)) {
        // (403) + 6 dígitos (gramos, etiqueta lote peso)
        tryInsertBefore(/^(.*)(403)(\d{6})$/);
    }
    return b;
}

/**
 * Algunos escáneres envían RS/US en lugar del FNC1/GS (0x1D) entre AIs; sin normalizar, el parser GS1 falla.
 */
patch(BarcodeParser.prototype, {
    parse_barcode(barcode) {
        if (typeof barcode === "string" && this.nomenclature?.is_gs1_nomenclature) {
            barcode = kcPreprocessPlasticasaGs1Scan(barcode, FNC1_CHAR);
        }
        return super.parse_barcode(...arguments);
    },
});

/**
 * Resuelve producto por referencia interna (default_code) cuando el segmento GS1 tipo producto
 * no coincide con product.barcode (p. ej. AI 240).
 */
patch(BarcodeModel.prototype, {
    async processBarcode(barcode, options = {}) {
        if (barcode && typeof barcode === "string" && this.parser?.nomenclature?.is_gs1_nomenclature) {
            barcode = kcPreprocessPlasticasaGs1Scan(barcode, FNC1_CHAR);
        }
        return super.processBarcode(barcode, options);
    },
    cleanBarcode(barcode) {
        let b = super.cleanBarcode(...arguments);
        if (typeof b === "string" && this.parser?.nomenclature?.is_gs1_nomenclature) {
            b = kcPreprocessPlasticasaGs1Scan(b, FNC1_CHAR);
        }
        return b;
    },
    async _processGs1Data(data, filters) {
        const result = await super._processGs1Data(...arguments);
        const { type, value } = data;
        if (type === "product" && value && !result.product && !result.packaging) {
            const products = await this.orm.searchRead(
                "product.product",
                [["default_code", "=", value]],
                ["id"],
                { limit: 2 },
            );
            if (products.length === 1) {
                result.product = await this.cache.getRecord("product.product", products[0].id);
                result.match = true;
            }
        }
        return result;
    },
});

function kcAddInLineUom(add, argsUom, lineUom) {
    if (!add) {
        return 0;
    }
    if (!argsUom || argsUom.id === lineUom.id) {
        return add;
    }
    if (argsUom.category_id !== lineUom.category_id) {
        return add;
    }
    return (add / argsUom.factor) * lineUom.factor;
}

function kcProjectedMoveQtyInMoveUom(pageLines, line, addInLineUom, cache) {
    if (!line.move_id) {
        return 0;
    }
    const moveRec = cache.getRecord("stock.move", line.move_id);
    if (!moveRec) {
        return 0;
    }
    const moveUom = cache.getRecord("uom.uom", moveRec.product_uom);
    let total = 0;
    for (const l of pageLines) {
        if (l.move_id !== line.move_id) {
            continue;
        }
        let q = l.qty_done;
        if (l.virtual_id === line.virtual_id) {
            q += addInLineUom;
        }
        const lu = l.product_uom_id;
        if (lu.category_id === moveUom.category_id) {
            total += (q / lu.factor) * moveUom.factor;
        } else {
            total += q;
        }
    }
    return total;
}

/**
 * Salidas: bloquear escaneo si lote baja calidad no permitido o si se supera tolerancia de excedente.
 */
patch(BarcodePickingModel.prototype, {
    async updateLine(line, args) {
        if (this.record.picking_type_code === "outgoing" && line.product_id) {
            const addRaw = args.qty_done || 0;
            const lineUom = line.product_uom_id;
            const addLine = kcAddInLineUom(addRaw, args.uom, lineUom);
            const lotId =
                (args.lot_id && (typeof args.lot_id === "number" ? args.lot_id : args.lot_id.id)) ||
                (line.lot_id && line.lot_id.id) ||
                false;
            const lotName =
                args.lot_name || line.lot_name || (line.lot_id && line.lot_id.name) || false;
            const moveId = line.move_id || args.move_id;
            const projected = kcProjectedMoveQtyInMoveUom(this.pageLines, line, addLine, this.cache);
            const res = await this.orm.call("stock.picking", "kc_barcode_check_outgoing_scan", [
                this.resId,
                {
                    move_id: moveId || false,
                    product_id: line.product_id.id,
                    lot_id: lotId,
                    lot_name: lotName,
                    qty_delta: addRaw,
                    projected_move_qty: projected,
                    product_uom_id: line.product_uom_id.id,
                },
            ]);
            if (res && res.error) {
                this.notification(res.message, { type: "danger" });
                return;
            }
        }
        await super.updateLine(...arguments);
    },
});
