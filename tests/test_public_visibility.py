from invoiceguard.public_visibility import item_visibility, train_eligible


def _item(**kw):
    base = {"description": "Consulting Services", "quantity": 5.0, "unit_price": 150.0, "amount": 750.0}
    base.update(kw)
    return base


def test_formal_corporate_all_visible():
    assert set(item_visibility("formal_corporate", _item()).values()) == {"visible_exact"}


def test_event_ticket_unit_price_never_printed_and_case_transformed():
    vis = item_visibility("event_ticket", _item())
    assert vis["unit_price"] == "not_printed"
    assert vis["description"] == "case_transformed"
    assert vis["quantity"] == vis["amount"] == "visible_exact"


def test_pos_thermal_unit_price_printed_only_when_differs_from_amount():
    assert item_visibility("pos_thermal", _item(quantity=1.0, unit_price=7.25, amount=7.25))["unit_price"] == "not_printed"
    assert item_visibility("pos_thermal", _item(quantity=2.0, unit_price=18.5, amount=37.0))["unit_price"] == "visible_exact"


def test_pos_thermal_description_truncated_at_28():
    assert item_visibility("pos_thermal", _item(description="x" * 28))["description"] == "visible_exact"
    assert item_visibility("pos_thermal", _item(description="x" * 29))["description"] == "truncated_by_renderer"


def test_two_decimal_printing_masks_more_precise_labels():
    assert item_visibility("utility_bill", _item(unit_price=0.125, amount=0.63))["unit_price"] == "printed_rounded"
    assert item_visibility("formal_corporate", _item(quantity=1.333))["quantity"] == "printed_rounded"
    assert item_visibility("utility_bill", _item(quantity=1.333))["quantity"] == "visible_exact"


def test_unknown_template_is_unverified():
    assert set(item_visibility("delivery_note", _item()).values()) == {"visibility_unverified"}


def test_train_eligibility():
    ok = {"_template_used": "modern_minimal", "line_items": [_item()]}
    assert train_eligible(ok) == (True, None)
    bad = {"_template_used": "event_ticket", "line_items": [_item()]}
    assert train_eligible(bad)[0] is False
    assert train_eligible({"_template_used": "modern_minimal", "line_items": []}) == (False, "no_line_items")
