# Failure analysis — m1_dev_v1

trade documents: 96, with any field error: 32

| cause | count |
|---|---:|
| quantity_raw:number_value | 22 |
| sku_raw:sku_raw_text | 20 |
| unit_price_raw:number_value | 17 |
| line_total_raw:number_value | 16 |
| description_raw:description_text | 16 |
| rows:missing | 7 |
| line_total_raw:number_format_only | 6 |
| subtotal_raw:number_format_only | 5 |
| total_raw:number_format_only | 5 |
| quantity_raw:ambiguous_quantity_text | 4 |
| invoice_number_raw:invoice_number_raw_text | 2 |
| unit_raw:unit_text | 1 |
| unit_price_raw:number_format_only | 1 |

## Examined (fixed order)
- `tr_094c507908ef__blur_jpeg`: line_total_raw:number_value
- `tr_3d6c316a6402__skew_lowres`: sku_raw:sku_raw_text
- `tr_489dcc965b4b`: subtotal_raw:number_format_only, total_raw:number_format_only
- `tr_489dcc965b4b__blur_jpeg`: subtotal_raw:number_format_only, total_raw:number_format_only
- `tr_489dcc965b4b__fade_noise`: subtotal_raw:number_format_only, total_raw:number_format_only
- `tr_5ed7bf6fba3c`: line_total_raw:number_format_only
- `tr_5ed7bf6fba3c__fade_noise`: unit_price_raw:number_value
- `tr_69cab78e7dcd`: line_total_raw:number_value
- `tr_69cab78e7dcd__fade_noise`: line_total_raw:number_format_only, subtotal_raw:number_format_only, total_raw:number_format_only
- `tr_69cab78e7dcd__skew_lowres`: line_total_raw:number_format_only, subtotal_raw:number_format_only, total_raw:number_format_only
