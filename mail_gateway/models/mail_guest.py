# Copyright 2024 Dixmit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

from odoo.addons.mail.tools.discuss import Store


class MailGuest(models.Model):
    _inherit = "mail.guest"

    gateway_id = fields.Many2one("mail.gateway")
    gateway_token = fields.Char()

    def _to_store(self, store: Store, fields):
        # NOTE: Odoo 19 no longer defines a base ``_to_store`` for
        # ``mail.guest`` (only ``_to_store_defaults``), so there is no
        # ``super()`` implementation left to call here. Replicate the
        # generic fallback used by core models without their own
        # ``_to_store`` (see ``discuss.channel._to_store``).
        store.add_records_fields(self, fields)
        if not fields or "gateway_id" in fields:
            for record in self:
                # see note above: store.add() would recurse into _to_store()
                store.add_records_fields(
                    record, {"gateway": {"id": record.gateway_id.id}}
                )
