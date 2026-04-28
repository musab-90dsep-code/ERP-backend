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
    Shop,
    Employee, Attendance, EmployeeTransaction, Contact, ContactEmployee,
    Product, Invoice, InvoiceItem, Payment, Check, InternalAccount,
    ProcessingOrder, Order, StockHistory, DailyExpense, AddMoney
)

# Import Serializers
from app.serializers import (
    ShopSerializer,
    EmployeeSerializer, AttendanceSerializer, EmployeeTransactionSerializer,
    ContactSerializer, ContactEmployeeSerializer, ProductSerializer,
    InvoiceSerializer, InvoiceItemSerializer, PaymentSerializer, CheckSerializer,
    InternalAccountSerializer, ProcessingOrderSerializer, OrderSerializer, StockHistorySerializer, DailyExpenseSerializer, AddMoneySerializer
)

# Mapping string names to their respective models and serializers
MODEL_REGISTRY = {
    'shop': (Shop, ShopSerializer),
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

# ========================================================
# 🚀 OPTIMIZATION: N+1 Query Mapping Setup
# ========================================================
SELECT_RELATED_MAP = {
    'invoice': ['contact'],
    'payment': ['contact', 'invoice'],
    'employee_transaction': ['employee'],
    'attendance': ['employee'],
    'processing_order': ['processor', 'product'],
    'stock_history': ['product'],
    'invoice_item': ['invoice', 'product']
}

PREFETCH_RELATED_MAP = {
    'invoice': ['items', 'payments', 'items__product']
}

class UnifiedAPIView(APIView):
    """
    A single API endpoint to handle all operations for all models. (Optimized)
    """
    
    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        model_name = request.data.get('model')
        obj_id = request.data.get('id')
        data = request.data.get('data', {})
        role = request.data.get('role', 'member')


        shop_id = request.data.get('shop_id')
        if shop_id and model_name != 'shop':
            if isinstance(data, dict):
                data['shop'] = shop_id
            elif data is None:
                data = {'shop': shop_id}

        if not action:
            return Response({'error': 'Missing "action" in request payload.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # ========================================================
        # 🛡️ SECURITY: ROLE-BASED ACCESS CONTROL
        # ========================================================
        if action in ['create', 'update', 'delete', 'bulk_delete']:
            if role == 'member':
                return Response({'error': 'Members are restricted to view and download only.'}, status=status.HTTP_403_FORBIDDEN)
            
            if role == 'manager':
                if model_name == 'employee':
                    return Response({'error': 'Managers cannot manage employee records.'}, status=status.HTTP_403_FORBIDDEN)
                
                if action in ['delete', 'bulk_delete'] and model_name in ['invoice', 'payment']:
                    return Response({'error': 'Managers cannot delete invoices or transactions.'}, status=status.HTTP_403_FORBIDDEN)

        # ========================================================
        # 🌟 SPECIAL: DASHBOARD STATS (Optimized Queries)
        # ========================================================
        if action == 'stats':
            now = timezone.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

            # Basic Counts
            total_products = Product.objects.filter(shop_id=shop_id).count() if shop_id else Product.objects.count()
            total_invoices = Invoice.objects.filter(shop_id=shop_id).count() if shop_id else Invoice.objects.count()
            total_employees = Employee.objects.filter(shop_id=shop_id).count() if shop_id else Employee.objects.count()
            total_checks = Check.objects.filter(shop_id=shop_id).count() if shop_id else Check.objects.count()
            
            # Sub-stats
            attendance_present = Attendance.objects.filter(date=today_start.date(), status='present', **({'shop_id': shop_id} if shop_id else {})).count()
            bounced_checks = CheckSerializer(Check.objects.filter(status='bounced', **({'shop_id': shop_id} if shop_id else {}))[:5], many=True, context={'request': request}).data
            low_stock_items = ProductSerializer(Product.objects.filter(stock_quantity__lte=5, **({'shop_id': shop_id} if shop_id else {}))[:5], many=True, context={'request': request}).data
            
            # Fetch base querysets
            payments_in = Payment.objects.filter(type='in', **({'shop_id': shop_id} if shop_id else {}))
            add_money = AddMoney.objects.filter(**({'shop_id': shop_id} if shop_id else {}))
            payments_out = Payment.objects.filter(type='out', **({'shop_id': shop_id} if shop_id else {}))
            daily_exp = DailyExpense.objects.filter(status='paid', **({'shop_id': shop_id} if shop_id else {}))
            emp_trans = EmployeeTransaction.objects.filter(type__in=['salary', 'advance', 'bonus', 'allowance', 'overtime', 'overtime_allowance'], **({'shop_id': shop_id} if shop_id else {}))

            # Sales by period (Total Cash In)
            # ─── OPTIMIZED AGGREGATIONS (One query per model instead of many) ───
            def get_period_stats(qs, field):
                return qs.aggregate(
                    day=Sum(Case(When(date__gte=today_start.date(), then=F(field)), default=Value(0), output_field=DecimalField())),
                    week=Sum(Case(When(date__gte=week_start.date(), then=F(field)), default=Value(0), output_field=DecimalField())),
                    month=Sum(Case(When(date__gte=month_start.date(), then=F(field)), default=Value(0), output_field=DecimalField())),
                    year=Sum(Case(When(date__gte=year_start.date(), then=F(field)), default=Value(0), output_field=DecimalField())),
                    total=Sum(field)
                )

            p_in_stats = get_period_stats(payments_in, 'amount')
            am_stats = get_period_stats(add_money, 'amount')

            sales_by_period = {
                k: float((p_in_stats[k] or 0) + (am_stats[k] or 0)) 
                for k in ['day', 'week', 'month', 'year']
            }
            current_total_received = float((p_in_stats['total'] or 0) + (am_stats['total'] or 0))

            p_out_stats = get_period_stats(payments_out, 'amount')
            de_stats = get_period_stats(daily_exp, 'total_amount')
            et_stats = get_period_stats(emp_trans, 'amount')

            expenses_by_period = {
                k: float((p_out_stats[k] or 0) + (de_stats[k] or 0) + (et_stats[k] or 0))
                for k in ['day', 'week', 'month', 'year']
            }
            current_total_paid = float((p_out_stats['total'] or 0) + (de_stats['total'] or 0) + (et_stats['total'] or 0))

            # Balance Calculations
            running_balance = current_total_received - current_total_paid
            
            # Total Due Calculation
            total_sell_amount = float(Invoice.objects.filter(type__in=['sell', 'exchange'], **({'shop_id': shop_id} if shop_id else {})).aggregate(s=Sum('total'))['s'] or 0)
            total_sell_payments = float(Payment.objects.filter(invoice__type__in=['sell', 'exchange'], **({'shop_id': shop_id} if shop_id else {})).aggregate(s=Sum('amount'))['s'] or 0)
            total_due = total_sell_amount - total_sell_payments

            # Stock Value Calculation
            current_stock_val = float(Product.objects.filter(**({'shop_id': shop_id} if shop_id else {})).aggregate(total=Sum(F('stock_quantity') * F('price'), output_field=DecimalField()))['total'] or 0)
            running_stock_val = current_stock_val
            running_due = total_due

            # ========================================================
            # 🚀 OPTIMIZED: AGGREGATE 7-DAY HISTORY VIA DB
            # ========================================================
            seven_days_ago_date = today_start.date() - timedelta(days=7)
            
            def get_daily_sums(queryset, amount_field, date_field='date'):
                return dict(queryset.filter(**{f"{date_field}__gte": seven_days_ago_date})
                            .values(date_field)
                            .annotate(total=Sum(amount_field))
                            .values_list(date_field, 'total'))

            sums_p_in = get_daily_sums(Payment.objects.filter(type='in', **({'shop_id': shop_id} if shop_id else {})), 'amount')
            sums_am = get_daily_sums(AddMoney.objects.filter(**({'shop_id': shop_id} if shop_id else {})), 'amount')
            sums_p_out = get_daily_sums(Payment.objects.filter(type='out', **({'shop_id': shop_id} if shop_id else {})), 'amount')
            sums_de = get_daily_sums(DailyExpense.objects.filter(status='paid', **({'shop_id': shop_id} if shop_id else {})), 'total_amount')
            sums_et = get_daily_sums(EmployeeTransaction.objects.filter(type__in=['salary', 'advance', 'bonus', 'allowance', 'overtime', 'overtime_allowance'], **({'shop_id': shop_id} if shop_id else {})), 'amount')
            
            sums_sh = dict(StockHistory.objects.filter(created_at__date__gte=seven_days_ago_date, **({'shop_id': shop_id} if shop_id else {}))
                           .values('created_at__date')
                           .annotate(total=Sum(F('quantity_added') * F('product__price'), output_field=DecimalField()))
                           .values_list('created_at__date', 'total'))

            sums_inv_sell = get_daily_sums(Invoice.objects.filter(type__in=['sell', 'exchange'], **({'shop_id': shop_id} if shop_id else {})), 'total')
            sums_pay_sell = get_daily_sums(Payment.objects.filter(invoice__type__in=['sell', 'exchange'], **({'shop_id': shop_id} if shop_id else {})), 'amount')
            seven_days_ago_date = today_start.date() - timedelta(days=7)

            sales_history, expenses_history, balance_history, stock_history_values, due_history = [], [], [], [], []

            for i in range(7):
                target_date = today_start.date() - timedelta(days=i)
                
                day_received = float(sums_p_in.get(target_date, 0) or 0) + float(sums_am.get(target_date, 0) or 0)
                day_paid = float(sums_p_out.get(target_date, 0) or 0) + float(sums_de.get(target_date, 0) or 0) + float(sums_et.get(target_date, 0) or 0)

                sales_history.append(day_received)
                expenses_history.append(day_paid)
                
                balance_history.append(running_balance)
                running_balance -= (day_received - day_paid)
                
                stock_history_values.append(running_stock_val)
                day_stock_change_val = float(sums_sh.get(target_date, 0) or 0)
                running_stock_val -= day_stock_change_val
                
                due_history.append(running_due)
                day_sell_amount = float(sums_inv_sell.get(target_date, 0) or 0)
                day_sell_payment = float(sums_pay_sell.get(target_date, 0) or 0)
                running_due -= (day_sell_amount - day_sell_payment)
            
            sales_history.reverse()
            expenses_history.reverse()
            balance_history.reverse()
            stock_history_values.reverse()
            due_history.reverse()

            # Recents
            recent_employees = EmployeeSerializer(Employee.objects.filter(**({'shop_id': shop_id} if shop_id else {})).order_by('-created_at')[:5], many=True, context={'request': request}).data
            recent_inv_qs = Invoice.objects.filter(**({'shop_id': shop_id} if shop_id else {})).select_related('contact').prefetch_related('items__product', 'payments').order_by('-created_at')[:5]
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
        # 🌟 SPECIAL: CASHBOOK LOGS (Safety Limit Added)
        # ========================================================
        if action == 'cashbook_logs':
            limit = 1000 # Added to prevent server memory crashes
            
            all_p_in = Payment.objects.filter(type='in', **({'shop_id': shop_id} if shop_id else {})).select_related('contact').order_by('-date', '-created_at')[:limit]
            all_am = AddMoney.objects.filter(**({'shop_id': shop_id} if shop_id else {})).order_by('-date', '-created_at')[:limit]
            
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
            full_inflow = full_inflow[:limit]

            all_p_out = Payment.objects.filter(type='out', **({'shop_id': shop_id} if shop_id else {})).select_related('contact', 'invoice').order_by('-date', '-created_at')[:limit]
            all_de = DailyExpense.objects.filter(**({'shop_id': shop_id} if shop_id else {})).order_by('-date', '-created_at')[:limit]
            all_et = EmployeeTransaction.objects.filter(type__in=['salary', 'advance', 'bonus', 'allowance', 'overtime', 'overtime_allowance'], **({'shop_id': shop_id} if shop_id else {})).select_related('employee').order_by('-date', '-created_at')[:limit]
            
            full_outflow = []
            for p in all_p_out:
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
            full_outflow = full_outflow[:limit]

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

            # 1. LIST (N+1 Query Optimized)
            if action == 'list':
                queryset = ModelClass.objects.all()
                
                # Apply Dynamic Select & Prefetch Related
                if model_name in SELECT_RELATED_MAP:
                    queryset = queryset.select_related(*SELECT_RELATED_MAP[model_name])
                if model_name in PREFETCH_RELATED_MAP:
                    queryset = queryset.prefetch_related(*PREFETCH_RELATED_MAP[model_name])
                
                if isinstance(data, dict) and data:
                    ordering = data.pop('ordering', None)
                    search = data.pop('search', None) 
                    limit = data.pop('limit', None)
                    
                    if data:
                        queryset = queryset.filter(**data)
                    
                    if ordering:
                        if isinstance(ordering, list):
                            queryset = queryset.order_by(*ordering)
                        else:
                            queryset = queryset.order_by(ordering)
                            
                    if limit:
                        try:
                            limit_val = int(limit)
                            if limit_val > 0:
                                queryset = queryset[:limit_val]
                        except ValueError:
                            pass

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

            # 8. SPECIAL: CONTACT DUE BALANCE
            elif action == 'due' and model_name == 'contact':
                if not obj_id:
                    return Response({'error': 'Missing "id" for contact due.'}, status=status.HTTP_400_BAD_REQUEST)
                
                contact_type = data.get('type', 'customer')
                
                # We calculate due strictly using DB aggregates to prevent memory overload
                if contact_type == 'customer' or contact_type == 'in':
                    total_sell_due = float(Invoice.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='sell').aggregate(s=Sum('due_amount'))['s'] or 0)
                    
                    ret_1 = float(Invoice.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='return').aggregate(s=Sum('total'))['s'] or 0)
                    ret_2 = float(Invoice.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='exchange', total__lt=0).aggregate(s=Sum('total'))['s'] or 0)
                    total_return_credit = abs(ret_1) + abs(ret_2)
                    
                    exchange_invoice_ids = list(Invoice.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='exchange', total__lt=0).values_list('id', flat=True))
                    cash_refunds = float(Payment.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='out', invoice_id__in=exchange_invoice_ids).aggregate(s=Sum('amount'))['s'] or 0)
                    
                    standalone_in = float(Payment.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='in', invoice__isnull=True).aggregate(s=Sum('amount'))['s'] or 0)
                    standalone_out = float(Payment.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='out', invoice__isnull=True).aggregate(s=Sum('amount'))['s'] or 0)
                    
                    due = total_sell_due - total_return_credit - cash_refunds - (standalone_in - standalone_out)
                    
                else: # supplier or out
                    total_buy_due = float(Invoice.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='buy').aggregate(s=Sum('due_amount'))['s'] or 0)
                    total_return_due = float(Invoice.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='return').aggregate(s=Sum('due_amount'))['s'] or 0)
                    
                    standalone_in = float(Payment.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='in', invoice__isnull=True).aggregate(s=Sum('amount'))['s'] or 0)
                    standalone_out = float(Payment.objects.filter(contact_id=obj_id, **({'shop_id': shop_id} if shop_id else {}), type='out', invoice__isnull=True).aggregate(s=Sum('amount'))['s'] or 0)
                    
                    due = (total_buy_due - total_return_due) - (standalone_out - standalone_in)

                due = round(max(0, due), 2)
                return Response({'due': due}, status=status.HTTP_200_OK)

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