from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.constrains("pricelist_id", "company_id")
    def _check_line_pricelist_currency(self):
        self.order_line._check_line_pricelist()
