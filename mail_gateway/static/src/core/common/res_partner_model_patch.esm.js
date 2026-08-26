import {ResPartner} from "@mail/core/common/res_partner_model";
import {fields} from "@mail/core/common/record";
import {patch} from "@web/core/utils/patch";

// Odoo 19 dropped the `Persona` store model: personas are now the real server
// models `res.partner` and `mail.guest`. The gateway channels are only ever
// sent along partner data (see `mail_gateway/tools/discuss.py`), so the field
// belongs on `res.partner`.
patch(ResPartner.prototype, {
    setup() {
        super.setup(...arguments);
        this.gateway_channels = fields.Many("GatewayChannel");
    },
});
