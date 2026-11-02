from app.api.invoices import invoice_total

assert invoice_total([19.99]) == 19.99
assert invoice_total([10.005, 10.005]) == 20.01
print("invoice checks passed")
