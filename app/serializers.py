from rest_framework import serializers
from app.models import (
    Shop,
    Employee, Attendance, EmployeeTransaction, Contact, ContactEmployee,
    Product, Invoice, InvoiceItem, Payment, Check, InternalAccount,
    ProcessingOrder, Order, StockHistory, DailyExpense, AddMoney
)

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'

    def create(self, validated_data):
        employee = validated_data.get('employee')
        date = validated_data.get('date')
        status = validated_data.get('status', 'present')
        ot_amount = validated_data.get('ot_amount', 0)
        note = validated_data.get('note', '')
        attendance, created = Attendance.objects.update_or_create(
            employee=employee,
            date=date,
            defaults={'status': status, 'ot_amount': ot_amount, 'note': note}
        )
        return attendance

class EmployeeTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTransaction
        fields = '__all__'

class EmployeeSerializer(serializers.ModelSerializer):
    attendances = AttendanceSerializer(many=True, read_only=True)
    transactions = EmployeeTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'

class ContactEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactEmployee
        fields = '__all__'
        extra_kwargs = {'contact': {'required': False}}

class ContactSerializer(serializers.ModelSerializer):
    employees = ContactEmployeeSerializer(many=True, required=False)
    due = serializers.SerializerMethodField()
    total_due = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = '__all__'

    def get_due(self, obj):
        from django.db.models import Sum
        contact_type = obj.type
        if contact_type == 'customer' or contact_type == 'processor':
            total_invoiced = float(Invoice.objects.filter(
                contact=obj, type__in=['sell', 'exchange']
            ).aggregate(s=Sum('total'))['s'] or 0)

            total_returned = float(Invoice.objects.filter(
                contact=obj, type='return'
            ).aggregate(s=Sum('total'))['s'] or 0)

            total_received = float(Payment.objects.filter(
                contact=obj, type='in'
            ).aggregate(s=Sum('amount'))['s'] or 0)

            total_refunded = float(Payment.objects.filter(
                contact=obj, type='out'
            ).aggregate(s=Sum('amount'))['s'] or 0)

            due = (total_invoiced - total_returned) - (total_received - total_refunded)

        else:
            total_purchased = float(Invoice.objects.filter(
                contact=obj, type='buy'
            ).aggregate(s=Sum('total'))['s'] or 0)

            total_buy_returns = float(Invoice.objects.filter(
                contact=obj, type='return'
            ).aggregate(s=Sum('total'))['s'] or 0)

            total_paid_out = float(Payment.objects.filter(
                contact=obj, type='out'
            ).aggregate(s=Sum('amount'))['s'] or 0)

            total_received_back = float(Payment.objects.filter(
                contact=obj, type='in'
            ).aggregate(s=Sum('amount'))['s'] or 0)

            due = (total_purchased - total_buy_returns) - (total_paid_out - total_received_back)

        return round(due, 2)

    def get_total_due(self, obj):
        return self.get_due(obj)

    def create(self, validated_data):
        employees_data = validated_data.pop('employees', [])
        contact = Contact.objects.create(**validated_data)
        for emp_data in employees_data:
            ContactEmployee.objects.create(contact=contact, **emp_data)
        return contact

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_unit = serializers.ReadOnlyField(source='product.unit')
    class Meta:
        model = InvoiceItem
        fields = '__all__'
        extra_kwargs = {'invoice': {'required': False}}

class PaymentSerializer(serializers.ModelSerializer):
    contact_details = ContactSerializer(source='contact', read_only=True)
    class Meta:
        model = Payment
        fields = '__all__'

class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, required=False)
    payments = PaymentSerializer(many=True, read_only=True)
    contact_details = ContactSerializer(source='contact', read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        invoice = Invoice.objects.create(**validated_data)
        
        # --- Handle Order Partial Fulfillment ---
        order = invoice.order
        order_items_updated = False
        
        for item_data in items_data:
            item = InvoiceItem.objects.create(invoice=invoice, **item_data)
            
            # Update order items invoiced_quantity
            if order and order.items and item.product:
                if not order.is_return or not item.is_return:
                    for order_item in order.items:
                        # Match by product, head, and quality to be precise
                        match_product = str(order_item.get('product_id')) == str(item.product.id)
                        if order.is_return:
                            match_head = True
                            match_quality = True
                        else:
                            match_head = order_item.get('selected_head', '') == item.selected_head
                            match_quality = order_item.get('quality', '') == item.quality
                        
                        if match_product and match_head and match_quality:
                            qty = float(item.quantity)
                            current_invoiced = float(order_item.get('invoiced_quantity', 0))
                            order_item['invoiced_quantity'] = current_invoiced + qty
                            order_items_updated = True
                            break
            
            # Stock Update Logic
            if item.product:
                product = item.product
                product.refresh_from_db()
                stock_before = product.stock_quantity
                
                if invoice.type == 'return' or (invoice.type == 'exchange' and item.is_return):
                    product.returned_stock_quantity += item.quantity
                elif invoice.type == 'sell' or (invoice.type == 'exchange' and not item.is_return):
                    product.stock_quantity -= item.quantity
                    product.update_variant_stock(item.quality, item.selected_head, -item.quantity)
                
                product.save()
                
                # Create Stock History
                if invoice.type == 'return' or (invoice.type == 'exchange' and item.is_return):
                    qty_change = 0
                elif invoice.type in ['sell', 'exchange'] and not item.is_return:
                    qty_change = -item.quantity
                else:
                    qty_change = 0
                
                StockHistory.objects.create(
                    product=product,
                    shop=invoice.shop,
                    item_type=product.category,
                    item_name=product.name,
                    quantity_added=qty_change,
                    stock_before=stock_before,
                    stock_after=product.stock_quantity,
                    note=f"Invoice {invoice.type}: {invoice.id} {'(Return Part - Added to Returned Stock)' if item.is_return else ''}"
                )
                
        # --- Save Order Status if updated ---
        if order and order_items_updated:
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
                
            order.save(update_fields=['items', 'status'])
                
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        
        # --- Handle Order Quantities Reverse for Old Items ---
        order = instance.order
        order_items_updated = False
        
        if order and order.items:
            for item in instance.items.all():
                if item.product:
                    if not order.is_return or not item.is_return:
                        for order_item in order.items:
                            match_product = str(order_item.get('product_id')) == str(item.product.id)
                            if order.is_return:
                                match_head = True
                                match_quality = True
                            else:
                                match_head = order_item.get('selected_head', '') == item.selected_head
                                match_quality = order_item.get('quality', '') == item.quality
                            
                            if match_product and match_head and match_quality:
                                qty = float(item.quantity)
                                current_invoiced = float(order_item.get('invoiced_quantity', 0))
                                order_item['invoiced_quantity'] = max(0.0, current_invoiced - qty)
                                order_items_updated = True
                                break

        # 1. Reverse stock changes for all ORIGINAL items of this invoice
        for item in instance.items.all():
            if item.product:
                product = item.product
                product.refresh_from_db()
                if instance.type == 'return' or (instance.type == 'exchange' and item.is_return):
                    # Originally did NOT change stock_quantity, only returned_stock_quantity!
                    product.returned_stock_quantity = max(0, product.returned_stock_quantity - item.quantity)
                elif instance.type == 'sell' or (instance.type == 'exchange' and not item.is_return):
                    # Originally decreased stock, so now increase/revert it!
                    product.stock_quantity += item.quantity
                    product.update_variant_stock(item.quality, item.selected_head, item.quantity)
                # NOTE: 'buy' invoices never changed stock, so nothing to revert
                product.save()
        
        # 2. Delete original items
        instance.items.all().delete()
        
        # 3. Update basic fields on instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # 4. Create new items and apply their stock changes
        for item_data in items_data:
            item = InvoiceItem.objects.create(invoice=instance, **item_data)
            
            # --- Update order items invoiced_quantity ---
            if order and order.items and item.product:
                if not order.is_return or not item.is_return:
                    for order_item in order.items:
                        match_product = str(order_item.get('product_id')) == str(item.product.id)
                        if order.is_return:
                            match_head = True
                            match_quality = True
                        else:
                            match_head = order_item.get('selected_head', '') == item.selected_head
                            match_quality = order_item.get('quality', '') == item.quality
                        
                        if match_product and match_head and match_quality:
                            qty = float(item.quantity)
                            current_invoiced = float(order_item.get('invoiced_quantity', 0))
                            order_item['invoiced_quantity'] = current_invoiced + qty
                            order_items_updated = True
                            break
            
            if item.product:
                product = item.product
                product.refresh_from_db()
                stock_before = product.stock_quantity
                
                if instance.type == 'return' or (instance.type == 'exchange' and item.is_return):
                    # Returned products: ONLY go to returned_stock_quantity, NOT normal stock_quantity!
                    product.returned_stock_quantity += item.quantity
                elif instance.type == 'sell' or (instance.type == 'exchange' and not item.is_return):
                    # Sold/taken products: go out of stock!
                    product.stock_quantity -= item.quantity
                    product.update_variant_stock(item.quality, item.selected_head, -item.quantity)
                # NOTE: 'buy' invoices do NOT auto-add stock — user adds stock manually
                
                product.save()
                
                # Create Stock History
                if instance.type == 'return' or (instance.type == 'exchange' and item.is_return):
                    qty_change = 0
                elif instance.type in ['sell', 'exchange'] and not item.is_return:
                    qty_change = -item.quantity
                else:
                    qty_change = 0  # buy: no auto stock change
                
                StockHistory.objects.create(
                    product=product,
                    shop=instance.shop,
                    item_type=product.category,
                    item_name=product.name,
                    quantity_added=qty_change,
                    stock_before=stock_before,
                    stock_after=product.stock_quantity,
                    note=f"Updated Invoice {instance.type}: {instance.id} {'(Return Part - Added to Returned Stock)' if item.is_return else ''}"
                )
                
        # --- Save Order Status if updated ---
        if order and order_items_updated:
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
                
        return instance

class CheckSerializer(serializers.ModelSerializer):
    partner_details = ContactSerializer(source='partner', read_only=True)
    class Meta:
        model = Check
        fields = '__all__'

class InternalAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalAccount
        fields = '__all__'

class ProcessingOrderSerializer(serializers.ModelSerializer):
    processor_details = ContactSerializer(source='processor', read_only=True)
    product_details = ProductSerializer(source='product', read_only=True)
    class Meta:
        model = ProcessingOrder
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    contact_details = ContactSerializer(source='contact', read_only=True)
    class Meta:
        model = Order
        fields = '__all__'

class StockHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StockHistory
        fields = '__all__'

class DailyExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyExpense
        fields = '__all__'

class AddMoneySerializer(serializers.ModelSerializer):
    class Meta:
        model = AddMoney
        fields = '__all__'

class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = '__all__'
