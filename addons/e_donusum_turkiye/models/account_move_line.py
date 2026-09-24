# -*- coding: utf-8 -*-
"""
account.move.line extension for E-Dönüşüm Türkiye.
"""

from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_seller_item_code = fields.Char(
        string="Tedarikçi Ürün Kodu",
        help="UBL SellersItemIdentification kodu"
    )
    x_buyer_item_code = fields.Char(
        string="Alıcı Ürün Kodu",
        help="UBL BuyersItemIdentification kodu"
    )
    x_discount_amount = fields.Monetary(
        string="İskonto Tutarı",
        currency_field='currency_id',
        default=0.0
    )
    x_charge_amount = fields.Monetary(
        string="Artırım / Yuvarlama Tutarı",
        currency_field='currency_id',
        default=0.0
    )
