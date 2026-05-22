import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from app.models import Contact, Product, Invoice, InvoiceItem, Payment

def test_invoice_and_payment():
    print("Running end-to-end check for Invoices and Payments...")
    
    # Get or create a mock contact
    contact, _ = Contact.objects.get_or_create(
        name="Test Customer",
        type="customer",
        defaults={"shop_name": "Test Shop", "phone": "01700000000"}
    )
    print(f"Contact ready: {contact.id} - {contact.name}")

    # Get or create a mock product
    product, _ = Product.objects.get_or_create(
        name="Test Finish Product",
        category="finished-goods",
        defaults={"price": 120.00, "cost": 80.00, "stock_quantity": 100}
    )
    print(f"Product ready: {product.id} - {product.name}")

    # 1. Create an invoice
    invoice = Invoice.objects.create(
        type="sell",
        contact=contact,
        date="2026-05-21",
        subtotal=120.00,
        discount=10.00,
        total=110.00,
        paid_amount=110.00,
        due_amount=0.00,
        payment_status="paid"
    )
    print(f"Invoice created: {invoice.id}")

    # 2. Create invoice item
    item = InvoiceItem.objects.create(
        invoice=invoice,
        product=product,
        quantity=1,
        price=120.00,
        subtotal=120.00
    )
    print(f"Invoice item created: {item.id}")

    # 3. Create payment with payment_method_details
    details = {
        "receive_acc": "01712345678",
        "trx_id": "BKASH_TRX_99999",
        "date_time": "2026-05-21T14:30:00"
    }
    
    payment = Payment.objects.create(
        invoice=invoice,
        contact=contact,
        type="in",
        amount=110.00,
        method="bikash",
        payment_method_details=details
    )
    print(f"Payment created: {payment.id} with details: {payment.payment_method_details}")

    # 4. Read back and verify
    fetched_invoice = Invoice.objects.prefetch_related('payments', 'items').get(id=invoice.id)
    print("\n--- Verification ---")
    print(f"Fetched Invoice ID: {fetched_invoice.id}")
    print(f"Fetched Invoice Total: {fetched_invoice.total}")
    print(f"Fetched Invoice Paid Amount: {fetched_invoice.paid_amount}")
    
    payments = list(fetched_invoice.payments.all())
    print(f"Number of payments associated: {len(payments)}")
    if len(payments) > 0:
        first_payment = payments[0]
        print(f"Payment Method: {first_payment.method}")
        print(f"Payment Details Saved: {first_payment.payment_method_details}")
        assert first_payment.payment_method_details == details, "Payment details mismatch!"
        print("Success! Payment details match perfectly.")
    
    # 5. Clean up
    payment.delete()
    item.delete()
    invoice.delete()
    print("\nCleanup completed. Temporary test records deleted.")

if __name__ == "__main__":
    try:
        test_invoice_and_payment()
    except Exception as e:
        import traceback
        print(f"Test failed with error: {e}")
        traceback.print_exc()
