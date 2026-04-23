from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import F, Sum, DecimalField, Case, When, Value
from django.utils import timezone
from datetime import timedelta

# Import Models
from app.models import (
    Employee, Attendance, EmployeeTransaction, Contact, ContactEmployee,
    Product, Invoice, InvoiceItem, Payment, Check, InternalAccount,
    ProcessingOrder, Order, StockHistory, DailyExpense, AddMoney
)

# Import Serializers
from app.serializers import (
    EmployeeSerializer, AttendanceSerializer, EmployeeTransactionSerializer,
    ContactSerializer, ContactEmployeeSerializer, ProductSerializer,
    InvoiceSerializer, InvoiceItemSerializer, PaymentSerializer, CheckSerializer,
    InternalAccountSerializer, ProcessingOrderSerializer, OrderSerializer, StockHistorySerializer, DailyExpenseSerializer, AddMoneySerializer
)

# Mapping string names to their respective models and serializers
MODEL_REGISTRY = {
    'employee': (Employee, EmployeeSerializer),
    'attendance': (Attendance, AttendanceSerializer),
    'employee_transaction': (EmployeeTransaction, EmployeeTransactionSerializer),
    'contact': (Contact, ContactSerializer),
    'contact_employee': (ContactEmployee, ContactEmployeeSerializer),
    'product': (Product, ProductSerializer),
    'invoice': (Invoice, InvoiceSerializer),
    'invoice_item': (InvoiceItem, InvoiceItemSerializer),
    'payment': (Payment, PaymentSerializer),
    'check': (Check, CheckSerializer),
    'internal_account': (InternalAccount, InternalAccountSerializer),
    'processing_order': (ProcessingOrder, ProcessingOrderSerializer),
    'order': (Order, OrderSerializer),
    'stock_history': (StockHistory, StockHistorySerializer),
    'daily_expense': (DailyExpense, DailyExpenseSerializer),
    'add_money': (AddMoney, AddMoneySerializer),
}

class UnifiedAPIView(APIView):
    """
    A single API endpoint to handle all operations for all models.
    """
    
    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        model_name = request.data.get('model')
        obj_id = request.data.get('id')
        data = request.data.get('data', {})
        role = request.data.get('role', 'member')

        if not action:
            return Response({'error': 'Missing "action" in request payload.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # ========================================================
        # 🛡️ SECURITY: ROLE-BASED ACCESS CONTROL
        # ========================================================
        if action in ['create', 'update', 'delete', 'bulk_delete']:
            if role == 'member':
                return Response({'error': 'Members are restricted to view and download only.'}, status=status.HTTP_403_FORBIDDEN)
            
            if role == 'manager':
                # Managers cannot manage employees
                if model_name == 'employee':
                    return Response({'error': 'Managers cannot manage employee records.'}, status=status.HTTP_403_FORBIDDEN)
                
                # Managers cannot delete invoices or payments
                if action in ['delete', 'bulk_delete'] and model_name in ['invoice', 'payment']:
                    return Response({'error': 'Managers cannot delete invoices or transactions.'}, status=status.HTTP_403_FORBIDDEN)

        # ========================================================
        # 🌟 SPECIAL: DASHBOARD STATS (Bypasses Model Registry)
        # ========================================================
        if action == 'stats':
            now = timezone.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

            # Basic Counts
            total_products = Product.objects.count()
            total_invoices = Invoice.objects.count()
            total_employees = Employee.objects.count()
            total_checks = Check.objects.count()
            
            # Sub-stats
            attendance_present = Attendance.objects.filter(date=today_start.date(), status='present').count()
            bounced_checks = CheckSerializer(Check.objects.filter(status='bounced')[:5], many=True, context={'request': request}).data
            low_stock_items = ProductSerializer(Product.objects.filter(stock_quantity__lte=5)[:5], many=True, context={'request': request}).data
            
            # High-res history for graphs (last 7 days)
            sales_history = []
            expenses_history = []
            balance_history = []
            stock_history_values = []
            
            # Fetch base querysets
            sales = Invoice.objects.filter(type='sell')
            expenses = DailyExpense.objects.all()

            # Sales by period (Total Cash In: Payments In + Add Money)
            payments_in = Payment.objects.filter(type='in')
            add_money = AddMoney.objects.all()

            sales_by_period = {
                'day': float((payments_in.filter(date__gte=today_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                             (add_money.filter(date__gte=today_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
                'week': float((payments_in.filter(date__gte=week_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                              (add_money.filter(date__gte=week_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
                'month': float((payments_in.filter(date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                               (add_money.filter(date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
                'year': float((payments_in.filter(date__gte=year_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                              (add_money.filter(date__gte=year_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
            }
            
            payments_out = Payment.objects.filter(type='out')
            daily_exp = DailyExpense.objects.filter(status='paid')
            emp_trans = EmployeeTransaction.objects.filter(type__in=['salary', 'advance', 'bonus', 'allowance', 'overtime', 'overtime_allowance'])

            expenses_by_period = {
                'day': float((payments_out.filter(date__gte=today_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                             (daily_exp.filter(date__gte=today_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0) +
                             (emp_trans.filter(date__gte=today_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
                'week': float((payments_out.filter(date__gte=week_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                              (daily_exp.filter(date__gte=week_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0) +
                              (emp_trans.filter(date__gte=week_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
                'month': float((payments_out.filter(date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                               (daily_exp.filter(date__gte=month_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0) +
                               (emp_trans.filter(date__gte=month_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
                'year': float((payments_out.filter(date__gte=year_start.date()).aggregate(s=Sum('amount'))['s'] or 0) + 
                              (daily_exp.filter(date__gte=year_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0) +
                              (emp_trans.filter(date__gte=year_start.date()).aggregate(s=Sum('amount'))['s'] or 0)),
            }

            # Get current running totals as base for balance calculation
            current_total_received = float(payments_in.aggregate(s=Sum('amount'))['s'] or 0)
            current_total_received += float(add_money.aggregate(s=Sum('amount'))['s'] or 0)
            
            current_total_paid = float(payments_out.aggregate(s=Sum('amount'))['s'] or 0)
            current_total_paid += float(daily_exp.aggregate(s=Sum('total_amount'))['s'] or 0)
            current_total_paid += float(emp_trans.aggregate(s=Sum('amount'))['s'] or 0)
            
            running_balance = current_total_received - current_total_paid
            
            # Total Due Calculation (Total Sell + Exchange Invoices - Total Payments Received for those)
            total_sell_amount = float(Invoice.objects.filter(type__in=['sell', 'exchange']).aggregate(s=Sum('total'))['s'] or 0)
            total_sell_payments = float(Payment.objects.filter(invoice__type__in=['sell', 'exchange']).aggregate(s=Sum('amount'))['s'] or 0)
            total_due = total_sell_amount - total_sell_payments

            # Stock Value Calculation (keeping for base balance if needed, though removed from UI)
            current_stock_val = float(Product.objects.aggregate(
                total=Sum(F('stock_quantity') * F('price'), output_field=DecimalField())
            )['total'] or 0)
            running_stock_val = current_stock_val
            
            running_due = total_due
            due_history = []

            for i in range(7):
                target_date = today_start.date() - timedelta(days=i)
                
                # 1. Sales (Cash In) & Expenses (Cash Out) History
                day_received = float(payments_in.filter(date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                day_received += float(add_money.filter(date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                
                day_paid = float(payments_out.filter(date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                day_paid += float(daily_exp.filter(date=target_date).aggregate(s=Sum('total_amount'))['s'] or 0)
                day_paid += float(emp_trans.filter(date=target_date).aggregate(s=Sum('amount'))['s'] or 0)

                sales_history.append(day_received)
                expenses_history.append(day_paid)
                
                # 2. Balance History (Calculate backwards)
                balance_history.append(running_balance)
                running_balance -= (day_received - day_paid)
                
                # 3. Stock Value History
                stock_history_values.append(running_stock_val)
                day_stock_change_val = float(StockHistory.objects.filter(created_at__date=target_date).aggregate(v=Sum(F('quantity_added') * F('product__price'), output_field=DecimalField()))['v'] or 0)
                running_stock_val -= day_stock_change_val
                
                # 4. Due History
                due_history.append(running_due)
                day_sell_amount = float(Invoice.objects.filter(type__in=['sell', 'exchange'], date=target_date).aggregate(s=Sum('total'))['s'] or 0)
                day_sell_payment = float(Payment.objects.filter(invoice__type__in=['sell', 'exchange'], date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                running_due -= (day_sell_amount - day_sell_payment)
            
            sales_history.reverse()
            expenses_history.reverse()
            balance_history.reverse()
            stock_history_values.reverse()
            due_history.reverse()

            # Recents
            recent_employees = EmployeeSerializer(Employee.objects.select_related().order_by('-created_at')[:5], many=True, context={'request': request}).data
            recent_inv_qs = Invoice.objects.select_related('contact').prefetch_related('items__product', 'payments').order_by('-created_at')[:5]
            recent_invoices = InvoiceSerializer(recent_inv_qs, many=True, context={'request': request}).data

            return Response({
                'total_products': total_products,
                'total_invoices': total_invoices,
                'total_employees': total_employees,
                'total_checks': total_checks,
                'attendance_present': attendance_present,
                'total_balance': current_total_received - current_total_paid,
                'total_due': total_due,
                'total_stock_value': current_stock_val,
                'sales_by_period': sales_by_period,
                'expenses_by_period': expenses_by_period,
                'sales_history': sales_history,
                'expenses_history': expenses_history,
                'balance_history': balance_history,
                'stock_history_values': stock_history_values,
                'due_history': due_history,
                'recent_employees': recent_employees,
                'recent_invoices': recent_invoices,
                'low_stock_items': low_stock_items,
                'bounced_checks': bounced_checks
            }, status=status.HTTP_200_OK)

        # ========================================================
        # 🌟 SPECIAL: CASHBOOK LOGS (Full History)
        # ========================================================
        if action == 'cashbook_logs':
            # Full Inflow (Payments In + Add Money)
            all_p_in = Payment.objects.filter(type='in').select_related('contact').order_by('-date', '-created_at')
            all_am = AddMoney.objects.all().order_by('-date', '-created_at')
            
            full_inflow = []
            for p in all_p_in:
                full_inflow.append({
                    'id': p.id,
                    'type': 'payment',
                    'source': p.contact.name if p.contact else 'Direct',
                    'amount': float(p.amount),
                    'method': p.method,
                    'date': p.date.isoformat() if p.date else None,
                    'label': 'Collection'
                })
            for a in all_am:
                full_inflow.append({
                    'id': str(a.id),
                    'type': 'add_money',
                    'source': a.purpose or 'Internal',
                    'amount': float(a.amount),
                    'method': a.payment_method,
                    'date': a.date.isoformat() if a.date else None,
                    'label': 'Add Money'
                })
            full_inflow.sort(key=lambda x: x['date'] or '', reverse=True)

            # Full Outflow (Payments Out + Daily Expenses + Employee Transactions)
            all_p_out = Payment.objects.filter(type='out').select_related('contact').order_by('-date', '-created_at')
            all_de = DailyExpense.objects.all().order_by('-date', '-created_at')
            all_et = EmployeeTransaction.objects.filter(type__in=['salary', 'advance', 'bonus', 'allowance', 'overtime', 'overtime_allowance']).select_related('employee').order_by('-date', '-created_at')
            
            full_outflow = []
            for p in all_p_out:
                # Determine label based on invoice type
                label = 'Payment'
                if p.invoice:
                    if p.invoice.type == 'exchange':
                        label = 'Return Refund'
                    elif p.invoice.type == 'buy':
                        label = 'Supplier Payment'
                full_outflow.append({
                    'id': p.id,
                    'type': 'payment',
                    'source': p.contact.name if p.contact else 'Direct',
                    'amount': float(p.amount),
                    'method': p.method,
                    'date': p.date.isoformat() if p.date else None,
                    'label': label
                })
            for d in all_de:
                full_outflow.append({
                    'id': str(d.id),
                    'type': 'expense',
                    'source': d.item_name or 'General',
                    'amount': float(d.total_amount),
                    'method': 'Cash', 
                    'date': d.date.isoformat() if d.date else None,
                    'label': 'Expense'
                })
            for e in all_et:
                full_outflow.append({
                    'id': str(e.id),
                    'type': 'employee_transaction',
                    'source': e.employee.name if e.employee else 'Employee',
                    'amount': float(e.amount),
                    'method': 'Cash', 
                    'date': e.date.isoformat() if e.date else None,
                    'label': str(e.type).replace('_', ' ').title()
                })
            full_outflow.sort(key=lambda x: x['date'] or '', reverse=True)

            return Response({
                'unified_inflow': full_inflow,
                'unified_outflow': full_outflow,
            }, status=status.HTTP_200_OK)

        # ========================================================
        # DYNAMIC MODEL HANDLING
        # ========================================================
        try:
            if not model_name:
                return Response({'error': 'Missing "model" in request payload.'}, status=status.HTTP_400_BAD_REQUEST)
            
            model_name = model_name.lower()
            if model_name not in MODEL_REGISTRY:
                return Response({'error': f'Model "{model_name}" not supported.'}, status=status.HTTP_400_BAD_REQUEST)

            ModelClass, SerializerClass = MODEL_REGISTRY[model_name]

            # 1. LIST
            if action == 'list':
                queryset = ModelClass.objects.all()
                
                if isinstance(data, dict) and data:
                    ordering = data.pop('ordering', None)
                    search = data.pop('search', None) 
                    
                    if data:
                        queryset = queryset.filter(**data)
                    
                    if ordering:
                        if isinstance(ordering, list):
                            queryset = queryset.order_by(*ordering)
                        else:
                            queryset = queryset.order_by(ordering)

                serializer = SerializerClass(queryset, many=True, context={'request': request})
                return Response(serializer.data, status=status.HTTP_200_OK)

            # 2. RETRIEVE
            elif action == 'retrieve':
                if not obj_id:
                    return Response({'error': 'Missing "id" for retrieve action.'}, status=status.HTTP_400_BAD_REQUEST)
                obj = get_object_or_404(ModelClass, id=obj_id)
                serializer = SerializerClass(obj, context={'request': request})
                return Response(serializer.data, status=status.HTTP_200_OK)

            # 3. CREATE
            elif action == 'create':
                if model_name == 'attendance':
                    emp_id = data.get('employee')
                    att_date = data.get('date')
                    if emp_id and att_date:
                        existing = ModelClass.objects.filter(employee_id=emp_id, date=att_date).first()
                        if existing:
                            serializer = SerializerClass(existing, data=data, partial=True, context={'request': request})
                        else:
                            serializer = SerializerClass(data=data, context={'request': request})
                    else:
                        serializer = SerializerClass(data=data, context={'request': request})
                else:
                    serializer = SerializerClass(data=data, context={'request': request})

                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # 4. UPDATE
            elif action == 'update':
                if not obj_id:
                    return Response({'error': 'Missing "id" for update action.'}, status=status.HTTP_400_BAD_REQUEST)
                obj = get_object_or_404(ModelClass, id=obj_id)
                serializer = SerializerClass(obj, data=data, partial=True, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # 5. DELETE
            elif action == 'delete':
                if not obj_id:
                    return Response({'error': 'Missing "id" for delete action.'}, status=status.HTTP_400_BAD_REQUEST)
                obj = get_object_or_404(ModelClass, id=obj_id)
                obj.delete()
                return Response({'message': 'Deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

            # 6. BULK DELETE
            elif action == 'bulk_delete':
                if isinstance(data, dict) and data:
                    queryset = ModelClass.objects.filter(**data)
                    count = queryset.count()
                    queryset.delete()
                    return Response({"deleted": count}, status=status.HTTP_200_OK)
                return Response({"error": "No filters provided for bulk delete"}, status=status.HTTP_400_BAD_REQUEST)

            # 7. SPECIAL: PROCESSING BALANCES
            elif action == 'balances' and model_name == 'processing_order':
                results = ProcessingOrder.objects.values(
                    'processor__name', 
                    'processor__shop_name', 
                    'product__name',
                    'product__unit'
                ).annotate(
                    issued=Sum(Case(When(type='issued', then=F('quantity')), default=Value(0), output_field=DecimalField())),
                    received=Sum(Case(When(type='received', then=F('quantity')), default=Value(0), output_field=DecimalField())),
                ).annotate(
                    balance=F('issued') - F('received')
                ).order_by('processor__name')
                
                clean_results = []
                for r in results:
                    clean_results.append({
                        'processor_name': r['processor__name'],
                        'processor_shop': r['processor__shop_name'],
                        'product_name': r['product__name'],
                        'unit': r['product__unit'],
                        'issued': float(r['issued']),
                        'received': float(r['received']),
                        'balance': float(r['balance'])
                    })
                return Response(clean_results)

            else:
                return Response({'error': f'Action "{action}" not supported.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'trace': traceback.format_exc()}, status=500)


class FileUploadView(APIView):
    """
    Endpoint for uploading images/files to local media storage.
    """
    def post(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided in the request.'}, status=status.HTTP_400_BAD_REQUEST)
        
        file_name = default_storage.save(file.name, ContentFile(file.read()))
        file_url = request.build_absolute_uri(f'/media/{file_name}')
        
        return Response({'url': file_url}, status=status.HTTP_201_CREATED)