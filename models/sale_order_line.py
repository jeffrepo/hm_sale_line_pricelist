from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    line_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Lista de precios",
        check_company=True,
        ondelete="restrict",
        help="Dejar vacío para usar la lista de precios del pedido.",
    )

    @api.depends(
        "product_id", "product_uom", "product_uom_qty", "line_pricelist_id",
        "order_id.pricelist_id", "order_id.date_order",
    )
    def _compute_pricelist_item_id(self):
        inherited = self.filtered(lambda line: not line.line_pricelist_id)
        super(SaleOrderLine, inherited)._compute_pricelist_item_id()
        for line in self - inherited:
            line.pricelist_item_id = (
                line.line_pricelist_id._get_product_rule(
                    line.product_id,
                    quantity=line.product_uom_qty or 1.0,
                    uom=line.product_uom,
                    date=line._get_order_date(),
                )
                if line.product_id and not line.display_type else False
            )

    @api.depends("line_pricelist_id", "linked_line_id.line_pricelist_id")
    def _compute_price_unit(self):
        # Odoo keeps its tax mapping, attribute extras, combo allocation and
        # protection of invoiced/expense/manual prices.
        return super()._compute_price_unit()

    @api.depends("line_pricelist_id", "linked_line_id.line_pricelist_id")
    def _compute_discount(self):
        return super()._compute_discount()

    def _get_pricelist_price_context(self):
        context = super()._get_pricelist_price_context()
        if self.line_pricelist_id:
            context["pricelist"] = self.line_pricelist_id.id
        return context

    @api.onchange("line_pricelist_id")
    def _onchange_line_pricelist_id(self):
        self._apply_line_pricelist()

    def _apply_line_pricelist(self):
        lines = self.filtered(lambda line: not line.display_type)
        lines.with_context(force_price_recomputation=True)._compute_price_unit()
        lines._compute_discount()

    def write(self, values):
        if "line_pricelist_id" in values:
            changed = self.filtered(
                lambda line: line.line_pricelist_id.id != values["line_pricelist_id"]
            )
            if changed.filtered(lambda line: line.qty_invoiced or line.order_id.locked):
                raise ValidationError(_(
                    "No se puede cambiar la tarifa de una línea facturada o de un pedido bloqueado."
                ))
        result = super().write(values)
        if "line_pricelist_id" in values and "price_unit" not in values:
            # Imports and RPC writes must behave like the form, even if the
            # previous price was entered manually.
            self._apply_line_pricelist()
        return result

    def _get_protected_fields(self):
        return super()._get_protected_fields() + ["line_pricelist_id"]

    @api.constrains("line_pricelist_id", "currency_id", "company_id", "display_type", "is_downpayment", "is_expense", "combo_item_id")
    def _check_line_pricelist(self):
        for line in self.filtered("line_pricelist_id"):
            pricelist = line.line_pricelist_id
            if pricelist.currency_id != line.currency_id:
                raise ValidationError(_("La lista de la línea debe usar la misma moneda que el pedido."))
            if pricelist.company_id and pricelist.company_id != line.company_id:
                raise ValidationError(_("La lista de la línea debe pertenecer a la compañía del pedido."))
            if line.display_type or line.is_downpayment or line.is_expense or line.combo_item_id:
                raise ValidationError(_(
                    "Seleccione la tarifa en una línea de producto o en el producto principal del combo; "
                    "no en notas, anticipos, gastos ni componentes del combo."
                ))
