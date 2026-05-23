from django.db import models
from django.contrib.auth.models import User
import uuid

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('member', 'Member'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    permissions = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.user.username} ({self.role})"

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
    
    # New Extended Fields
    father_name = models.CharField(max_length=255, null=True, blank=True)
    mother_name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    marriage_status = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, default='Active', null=True, blank=True)
    salary_period = models.CharField(max_length=50, default='Monthly', null=True, blank=True)
    employment_type = models.CharField(max_length=50, default='Full-time', null=True, blank=True) # Full-time, Part-time, Contract, etc.
    permanent_address = models.JSONField(default=dict, blank=True)
    local_address = models.JSONField(default=dict, blank=True)
    same_as_local = models.BooleanField(default=False, null=True, blank=True)
    emergency_contact = models.JSONField(default=dict, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name

class Attendance(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, default='present') # 'present', 'absent', 'half'
    ot_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(null=True, blank=True)
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
    payment_method = models.CharField(max_length=50, default='Cash')
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class Contact(models.Model):
    shop = models.ForeignKey('Shop', on_delete=models.CASCADE, null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=50, db_index=True) # 'customer', 'supplier', 'processor'
    customer_code = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=255)
    shop_name = models.CharField(max_length=255, null=True, blank=True)
    customer_type = models.CharField(max_length=50, default='Retail', null=True, blank=True) # 'Retail', 'Wholesale', 'VIP'
    phone = models.CharField(max_length=50, null=True, blank=True)
    whatsapp = models.CharField(max_length=50, null=True, blank=True)
    phone_numbers = models.JSONField(default=list, blank=True)
    email = models.EmailField(null=True, blank=True)
    website = models.URLField(max_length=500, null=True, blank=True)

    # Address fields
    country = models.CharField(max_length=100, default='Bangladesh', null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True) # District
    thana = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True) # Area (Street/House/Road)
    address_line_2 = models.TextField(null=True, blank=True)

    # ID / Legal
    id_type = models.CharField(max_length=100, default='National ID', null=True, blank=True)
    id_number = models.CharField(max_length=255, null=True, blank=True)
    tin_number = models.CharField(max_length=255, null=True, blank=True)

    # Financial
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, null=True, blank=True)
    customer_since = models.DateField(null=True, blank=True)

    # Other
    notes = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default='active', null=True, blank=True) # 'active', 'inactive'
    photo_url = models.URLField(max_length=1000, null=True, blank=True)
    bank_details = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.shop_name if self.shop_name else self.name

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
    notes = models.TextField(null=True, blank=True)
    returned_stock_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.variants:
            import json
            variants_list = self.variants
            if isinstance(variants_list, str):
                try:
                    variants_list = json.loads(variants_list)
                except Exception:
                    variants_list = []
            
            if isinstance(variants_list, list) and len(variants_list) > 0:
                total_stock = 0.0
                total_min_stock = 0.0
                for v in variants_list:
                    if isinstance(v, dict):
                        total_stock += float(v.get('stock') or 0.0)
                        total_min_stock += float(v.get('min_stock') or 0.0)
                self.stock_quantity = total_stock
                self.minimum_stock = total_min_stock
        super().save(*args, **kwargs)


    def update_variant_stock(self, quality, head, quantity_change):
        """
        Update a variant's stock by matching the variant name.
        Variant names are stored as:
          - "Quality - Head"  (combined)
          - "Head"            (head only)
          - "Quality"         (quality only)
        selected_head from frontend may contain:
          - Full variant name "Quality - Head"
          - Just the head part "Head"
          - Full variant name without quality
        """
        if not self.variants:
            return False
        q = (quality or "").strip()
        h = (head or "").strip()

        # Build candidates from most-specific to least-specific
        candidates = []
        if q and h:
            candidates.append(f"{q} - {h}")   # exact combo match
        if h:
            candidates.append(h)               # exact head match (or full name)
        if q:
            candidates.append(q)               # exact quality match

        # First pass: exact name match
        for candidate in candidates:
            for i, v in enumerate(self.variants):
                name = v.get('name', '')
                if name and name == candidate:
                    current_stock = float(v.get('stock') or 0)
                    self.variants[i]['stock'] = str(round(max(0.0, current_stock + float(quantity_change)), 3))
                    return True

        # Second pass: if head is given, match variants where name ends with " - {head}"
        # This handles the case where frontend sends head="Long Body" but DB has "Classic Series - Long Body"
        if h and q:
            suffix = f" - {h}"
            prefix = f"{q} - "
            for i, v in enumerate(self.variants):
                name = v.get('name', '')
                if name and name.endswith(suffix) and name.startswith(prefix):
                    current_stock = float(v.get('stock') or 0)
                    self.variants[i]['stock'] = str(round(max(0.0, current_stock + float(quantity_change)), 3))
                    return True
        elif h:
            suffix = f" - {h}"
            for i, v in enumerate(self.variants):
                name = v.get('name', '')
                if name and name.endswith(suffix):
                    current_stock = float(v.get('stock') or 0)
                    self.variants[i]['stock'] = str(round(max(0.0, current_stock + float(quantity_change)), 3))
                    return True

        return False

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
    due_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=255, null=True, blank=True)
    sales_person = models.CharField(max_length=255, null=True, blank=True)
    shipping = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    authorized_signature = models.CharField(max_length=255, null=True, blank=True)
    received_by = models.CharField(max_length=255, null=True, blank=True)
    prepared_by = models.CharField(max_length=255, null=True, blank=True)
    warehouse = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    order = models.ForeignKey('Order', null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def delete(self, *args, **kwargs):
        # Allow passing restock via kwargs if we manually call delete
        restock = kwargs.pop('restock', True)

        if restock:
            # Reverse stock change for all items
            for item in self.items.all():
                if item.product:
                    product = item.product
                    product.refresh_from_db()
                    stock_before = product.stock_quantity
                    if self.type == 'return' or (self.type == 'exchange' and item.is_return):
                        # Originally did NOT change stock_quantity, only returned_stock_quantity!
                        product.returned_stock_quantity = max(0, product.returned_stock_quantity - item.quantity)
                    elif self.type == 'sell' or (self.type == 'exchange' and not item.is_return):
                        # Originally decreased stock, so now increase/revert it!
                        product.stock_quantity += item.quantity
                        product.update_variant_stock(item.quality, item.selected_head, item.quantity)
                    # NOTE: 'buy' invoices never changed stock automatically, so nothing to revert
                    product.save()
                    
                    # Create Stock History for reversion
                    if self.type == 'return' or (self.type == 'exchange' and item.is_return):
                        qty_change = 0
                    elif self.type in ['sell', 'exchange'] and not item.is_return:
                        qty_change = item.quantity
                    else: # buy — no stock was changed, so nothing to revert
                        qty_change = 0
                    StockHistory.objects.create(
                        product=product,
                        shop=self.shop,
                        item_type=product.category,
                        item_name=product.name,
                        quantity_added=qty_change,
                        stock_before=stock_before,
                        stock_after=product.stock_quantity,
                        note=f"Reverted Stock: Deleted Invoice {self.type}: {self.id} {'(Return Part - Reverted Returned Stock)' if item.is_return else ''}"
                    )

        # --- Reverse Order items invoiced_quantity & Recalculate Order Status ---
        order = self.order
        if order and order.items:
            order_items_updated = False
            for item in self.items.all():
                if item.product:
                    for order_item in order.items:
                        # Match by product, head, and quality to be precise
                        match_product = str(order_item.get('product_id')) == str(item.product.id)
                        match_head = order_item.get('selected_head', '') == item.selected_head
                        match_quality = order_item.get('quality', '') == item.quality
                        
                        if match_product and match_head and match_quality:
                            qty = float(item.quantity)
                            current_invoiced = float(order_item.get('invoiced_quantity', 0))
                            order_item['invoiced_quantity'] = max(0.0, current_invoiced - qty)
                            order_items_updated = True
                            break
            
            if order_items_updated:
                # Recalculate order status
                all_delivered = True
                any_invoiced = False
                for o_item in order.items:
                    o_qty = float(o_item.get('quantity', 0))
                    i_qty = float(o_item.get('invoiced_quantity', 0))
                    if i_qty > 0:
                        any_invoiced = True
                    if i_qty < o_qty:
                        all_delivered = False
                
                if all_delivered:
                    order.status = 'delivered'
                elif any_invoiced:
                    order.status = 'partial'
                else:
                    order.status = 'pending'
                
                order.save(update_fields=['items', 'status'])

        super().delete(*args, **kwargs)

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
