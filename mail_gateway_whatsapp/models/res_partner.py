# Copyright 2024 Dixmit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["mail.thread.phone", "res.partner"]

    def _whatsapp_get_partner(self):
        return self

    def _phone_get_number_fields(self):
        """This method returns the fields to use to find the number to use to
        send an SMS on a record."""
        # Odoo 19 dropped res.partner.mobile (merged into phone). Guard by
        # field existence, the same way core phone_validation does, so the
        # override stays correct on both 18 and 19.
        result = set(super()._phone_get_number_fields())
        result.update(fname for fname in ("mobile", "phone") if fname in self._fields)
        return list(result)
