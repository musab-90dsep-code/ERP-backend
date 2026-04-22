from rest_framework import serializers
from app.models import (
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
        attendance, created = Attendance.objects.update_or_create(
            employee=employee,
            date=date,
            defaults={'status': status}
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

    class Meta:
        model = Contact
        fields = '__all__'

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
        
        for item_data in items_data:
            item = InvoiceItem.objects.create(invoice=invoice, **item_data)
            
            # Stock Update Logic
            if item.product:
                product = item.product
                stock_before = product.stock_quantity
                
                # Check if it's an exchange or specific type
                should_update_returned = False
                if invoice.type == 'return':
                    should_update_returned = True
                elif invoice.type == 'exchange' and item.is_return:
                    should_update_returned = True
                
                if should_update_returned:
                    product.returned_stock_quantity += item.quantity
                else:
                    if invoice.type == 'sell' or invoice.type == 'exchange':
                        product.stock_quantity -= item.quantity
                    elif invoice.type == 'buy':
                        product.stock_quantity += item.quantity
                
                product.save()
                
                # Create Stock History
                from app.models import StockHistory
                qty_change = -item.quantity if (invoice.type in ['sell', 'exchange'] and not item.is_return) else item.quantity
                
                StockHistory.objects.create(
                    product=product,
                    item_type=product.category,
                    item_name=product.name,
                    quantity_added=qty_change,
                    stock_before=stock_before,
                    stock_after=product.stock_quantity,
                    note=f"Invoice {invoice.type}: {invoice.id} {'(Return Part)' if item.is_return else ''}"
                )
                
        return invoice

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
