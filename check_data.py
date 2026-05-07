import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()

from app.models import Contact, ProcessingOrder

print("--- Processors ---")
processors = Contact.objects.filter(type='processor')
for p in processors:
    print(f"ID: {p.id}, Name: {p.name}, Shop: {p.shop_name}")

print("\n--- Processing Orders ---")
orders = ProcessingOrder.objects.all()
for o in orders:
    print(f"Type: {o.type}, Processor: {o.processor.name if o.processor else 'None'}, Product: {o.product.name if o.product else 'None'}, Qty: {o.quantity}")
