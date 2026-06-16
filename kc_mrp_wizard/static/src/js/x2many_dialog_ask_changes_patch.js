/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyFieldDialog } from "@web/views/fields/relational_utils";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";

/**
 * Antes de cerrar el diálogo de una línea x2many (p. ej. operación en la LdM), vacía los buffers
 * locales de los widgets (NEED_LOCAL_CHANGES). Sin esto, `record.dirty` puede seguir en false y
 * `validateExtendedRecord` sale antes de notificar al padre: la LdM nunca recibe el UPDATE y no hay
 * llamada a web_save (solo se ven onchange en el log).
 */
patch(X2ManyFieldDialog.prototype, {
    save({ saveAndNew }) {
        return executeButtonCallback(this.modalRef.el, async () => {
            await this.record.model._askChanges();
            if (await this.record.checkValidity({ displayNotification: true })) {
                await this.props.save(this.record);
                if (saveAndNew) {
                    await this.record.switchMode("readonly");
                    this.record = await this.props.addNew();
                }
            } else {
                return false;
            }
            if (!saveAndNew) {
                this.props.close();
            }
            return true;
        });
    },
});
