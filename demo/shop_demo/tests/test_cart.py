import pytest
from shop.cart import Cart


def test_add_new_item():
    c = Cart()
    c.add("pen", 10, 2)
    assert c.items["pen"]["qty"] == 2


def test_add_same_item_accumulates():
    c = Cart()
    c.add("pen", 10, 2)
    c.add("pen", 10, 3)
    assert c.items["pen"]["qty"] == 5


def test_subtotal():
    c = Cart()
    c.add("pen", 10, 2)
    c.add("book", 50)
    assert c.subtotal() == 70


def test_total_with_discount():
    c = Cart()
    c.add("book", 100)
    assert c.total(10) == 90.0


def test_negative_qty_rejected():
    with pytest.raises(ValueError):
        Cart().add("pen", 10, -1)
        