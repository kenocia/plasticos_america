/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { many2OneAvatarField } from "@web/views/fields/many2one_avatar/many2one_avatar_field";

const _extractProps = many2OneAvatarField.extractProps;

/**
 * many2one_avatar* fuerza canOpen=true en formularios y anula options.no_open.
 * Respeta no_open para ocultar el botón de enlace externo (oi-arrow-right).
 */
patch(many2OneAvatarField, {
    extractProps(...args) {
        const props = _extractProps(...args);
        const fieldInfo = args[0];
        if (fieldInfo.options?.no_open) {
            props.canOpen = false;
        }
        return props;
    },
});
