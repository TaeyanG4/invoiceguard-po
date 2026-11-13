# Failure analysis — b0_dev_v11

trade documents: 96, with any field error: 83

| cause | count |
|---|---:|
| rows:missing | 68 |
| discount_raw:missing_value | 26 |
| currency_raw:missing_value | 24 |
| tax_raw:missing_value | 20 |
| invoice_number_raw:missing_value | 18 |
| invoice_number_raw:invoice_number_raw_text | 17 |
| subtotal_raw:missing_value | 13 |
| total_raw:missing_value | 12 |
| tax_raw:number_value | 11 |
| subtotal_raw:number_value | 11 |
| quantity_raw:number_value | 11 |
| line_total_raw:number_value | 9 |
| discount_raw:number_value | 8 |
| sku_raw:sku_raw_text | 8 |
| sku_raw:missing_value | 8 |
| description_raw:description_text | 8 |
| unit_price_raw:missing_value | 7 |
| unit_raw:unit_text | 7 |
| unit_price_raw:number_value | 5 |
| total_raw:number_value | 5 |
| unit_raw:missing_value | 4 |
| quantity_raw:number_format_only | 3 |
| tax_raw:number_format_only | 2 |
| line_total_raw:missing_value | 2 |
| unit_price_raw:number_format_only | 2 |
| rows:excess | 1 |
| quantity_raw:missing_value | 1 |
| discount_raw:number_format_only | 1 |

## Examined (fixed order)
- `tr_01ed9dbd532f`: discount_raw:missing_value, tax_raw:number_value, unit_price_raw:number_value
- `tr_01ed9dbd532f__blur_jpeg`: currency_raw:missing_value, discount_raw:missing_value, invoice_number_raw:missing_value, rows:missing, subtotal_raw:missing_value, tax_raw:missing_value
- `tr_01ed9dbd532f__fade_noise`: discount_raw:number_value, invoice_number_raw:missing_value, rows:missing, tax_raw:number_value, total_raw:missing_value
- `tr_01ed9dbd532f__skew_lowres`: discount_raw:missing_value, rows:missing, tax_raw:missing_value
- `tr_094c507908ef__blur_jpeg`: rows:missing, subtotal_raw:number_value, tax_raw:missing_value, total_raw:missing_value
- `tr_094c507908ef__fade_noise`: quantity_raw:number_format_only
- `tr_094c507908ef__skew_lowres`: rows:missing
- `tr_0dc291e8cb69__blur_jpeg`: currency_raw:missing_value, discount_raw:missing_value, rows:missing, subtotal_raw:number_value, tax_raw:missing_value
- `tr_0dc291e8cb69__fade_noise`: discount_raw:missing_value, invoice_number_raw:missing_value, rows:missing
- `tr_0dc291e8cb69__skew_lowres`: rows:missing
