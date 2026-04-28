import uuid
from django.db import models

class Shop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    address = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    modules = models.JSONField(default=list, blank=True)  # e.g. ['inventory','employees','orders',...]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Employee(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, null=True, blank=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    phone = models.JSONField(default=list, blank=True)
    whatsapp = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    id_document_type = models.CharField(max_length=50, default='NID')
    id_document_number = models.CharField(max_length=255, null=True, blank=True)
    profile_image_url = models.URLField(max_length=1000, null=True, blank=True)
    id_photo_urls = models.JSONField(default=list, blank=True)
    daily_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_authorizer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name

class Attendance(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, default='present') # 'present', 'absent', 'half'
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('employee', 'date')

class EmployeeTransaction(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=50, db_index=True) # 'salary', 'advance', 'bonus', 'deduction'
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(db_index=True)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class Contact(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, db_index=True) # 'customer', 'supplier', 'processor'
    customer_code = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=255)
    shop_name = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    whatsapp = models.CharField(max_length=50, null=True, blank=True)
    phone_numbers = models.JSONField(default=list, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    photo_url = models.URLField(max_length=1000, null=True, blank=True)
    bank_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name

class ContactEmployee(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='employees')
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=100, default='Employee')
    phone = models.JSONField(default=list, blank=True)
    photo_url = models.URLField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Product(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, null=True, blank=True)
    category = models.CharField(max_length=100, default='finished-goods', db_index=True) # 'raw-materials', 'finished-goods'
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit = models.CharField(max_length=20, default='pcs')
    unit_value = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    barcode = models.CharField(max_length=100, null=True, blank=True)
    is_tracked = models.BooleanField(default=True)
    low_stock_alert = models.BooleanField(default=False)
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    use_for_processing = models.BooleanField(default=False)
    processing_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    processing_price_auto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    processing_price_manual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    image_urls = models.JSONField(default=list, blank=True)
    product_heads = models.JSONField(default=list, blank=True)
    variants = models.JSONField(default=list, blank=True)  # [{name: str, price: float}]
    product_quality = models.CharField(max_length=50, null=True, blank=True)
    returned_stock_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, db_index=True) # 'buy', 'sell', 'return'
    contact = models.ForeignKey(Contact, null=True, on_delete=models.SET_NULL, related_name='invoices')
    date = models.DateField(null=True, blank=True, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, default='unpaid', db_index=True)
    authorized_signature = models.CharField(max_length=255, null=True, blank=True)
    received_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class InvoiceItem(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selected_head = models.CharField(max_length=255, null=True, blank=True)
    quality = models.CharField(max_length=100, null=True, blank=True)
    is_return = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Payment(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, null=True, on_delete=models.SET_NULL, related_name='payments')
    contact = models.ForeignKey(Contact, null=True, on_delete=models.SET_NULL, related_name='payments')
    type = models.CharField(max_length=20, db_index=True) # 'in', 'out'
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, default='cash')
    date = models.DateField(auto_now_add=True, db_index=True)
    payment_method_details = models.JSONField(default=dict, blank=True)
    authorized_signature = models.CharField(max_length=255, null=True, blank=True)
    received_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class Check(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, db_index=True) # 'received', 'issued'
    check_number = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issue_date = models.DateField(null=True, blank=True)
    cash_date = models.DateField()
    alert_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, default='pending', db_index=True)
    partner = models.ForeignKey(Contact, null=True, on_delete=models.SET_NULL, related_name='checks')
    transfer_memo_no = models.CharField(max_length=100, null=True, blank=True)
    transfer_date = models.DateField(null=True, blank=True)
    transfer_auth_signature = models.CharField(max_length=255, null=True, blank=True)
    transfer_received_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class InternalAccount(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_type = models.CharField(max_length=50, db_index=True) # 'bank', 'wallet'
    provider_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=100)
    branch = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ProcessingOrder(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, db_index=True) # 'issued', 'received'
    memo_no = models.CharField(max_length=100, null=True, blank=True)
    processor = models.ForeignKey(Contact, null=True, on_delete=models.SET_NULL, related_name='processing_orders')
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL, related_name='processing_orders')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    date = models.DateField(db_index=True)
    process_type = models.CharField(max_length=50, null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    photo_urls = models.JSONField(default=list, blank=True)
    authorized_signature = models.CharField(max_length=255, null=True, blank=True)
    received_by = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class Order(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_no = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=50, db_index=True) # 'sales', 'purchase'
    contact = models.ForeignKey(Contact, null=True, on_delete=models.SET_NULL, related_name='orders')
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    items = models.JSONField(default=list, blank=True)
    is_return = models.BooleanField(default=False)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, default='pending', db_index=True)
    date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class StockHistory(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_histories')
    item_type = models.CharField(max_length=100, db_index=True) # 'raw-materials', 'finished-goods'
    item_name = models.CharField(max_length=255)
    quantity_added = models.DecimalField(max_digits=12, decimal_places=3)
    stock_before = models.DecimalField(max_digits=12, decimal_places=3)
    stock_after = models.DecimalField(max_digits=12, decimal_places=3)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.item_name} - {self.quantity_added} tracked at {self.created_at}"

class DailyExpense(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_no = models.CharField(max_length=100, unique=True)
    date = models.DateField(db_index=True)
    item_name = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, default='pcs')
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    price_per_unit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending', db_index=True) # 'pending', 'paid'
    photo_urls = models.JSONField(default=list, blank=True)
    authorized_signature = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class AddMoney(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memo_no = models.CharField(max_length=100, unique=True)
    date = models.DateField(db_index=True)
    purpose = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(null=True, blank=True)
    photo_urls = models.JSONField(default=list, blank=True)
    payment_method = models.CharField(max_length=50, default='cash')
    payment_method_details = models.JSONField(default=dict, blank=True)
    authorized_signature = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
