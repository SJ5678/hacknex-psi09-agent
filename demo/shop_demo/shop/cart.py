class Cart:
    def __init__(self):
        self.items = {}

    def add(self, name, price, qty=1):
        if qty <= 0:
            raise ValueError("qty must be positive")
        if name in self.items:
            self.items[name]["qty"] = qty      # BUG: should accumulate (+=)
        else:
            self.items[name] = {"price": price, "qty": qty}

    def subtotal(self):
        return sum(i["price"] * i["qty"] for i in self.items.values())

    def total(self, discount_percent=0):
        return round(self.subtotal() * (1 - discount_percent / 100), 2)
    