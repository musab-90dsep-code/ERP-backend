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

        if not action:
            return Response({'error': 'Missing "action" in request payload.'}, status=status.HTTP_400_BAD_REQUEST)
        
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

            # Sales by period summary
            sales_by_period = {
                'day': float(sales.filter(date__gte=today_start.date()).aggregate(s=Sum('total'))['s'] or 0),
                'week': float(sales.filter(date__gte=week_start.date()).aggregate(s=Sum('total'))['s'] or 0),
                'month': float(sales.filter(date__gte=month_start.date()).aggregate(s=Sum('total'))['s'] or 0),
                'year': float(sales.filter(date__gte=year_start.date()).aggregate(s=Sum('total'))['s'] or 0),
            }
            
            # Expenses by period summary
            expenses_by_period = {
                'day': float(expenses.filter(date__gte=today_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0),
                'week': float(expenses.filter(date__gte=week_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0),
                'month': float(expenses.filter(date__gte=month_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0),
                'year': float(expenses.filter(date__gte=year_start.date()).aggregate(s=Sum('total_amount'))['s'] or 0),
            }

            # Get current running totals as base
            current_total_received = float(Payment.objects.filter(type='in').aggregate(s=Sum('amount'))['s'] or 0)
            current_total_received += float(AddMoney.objects.aggregate(s=Sum('amount'))['s'] or 0)
            
            current_total_paid = float(Payment.objects.filter(type='out').aggregate(s=Sum('amount'))['s'] or 0)
            current_total_paid += float(DailyExpense.objects.filter(status='paid').aggregate(s=Sum('total_amount'))['s'] or 0)
            
            running_balance = current_total_received - current_total_paid
            
            # Stock Value Calculation
            current_stock_val = float(Product.objects.aggregate(
                total=Sum(F('stock_quantity') * F('price'), output_field=DecimalField())
            )['total'] or 0)
            running_stock_val = current_stock_val

            for i in range(7):
                target_date = today_start.date() - timedelta(days=i)
                
                # 1. Sales & Expenses (Daily sum)
                s_day = float(sales.filter(date=target_date).aggregate(s=Sum('total'))['s'] or 0)
                e_day = float(DailyExpense.objects.filter(date=target_date).aggregate(s=Sum('total_amount'))['s'] or 0)
                sales_history.append(s_day)
                expenses_history.append(e_day)
                
                # 2. Balance History (Calculate backwards)
                balance_history.append(running_balance)
                
                day_received = float(Payment.objects.filter(type='in', date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                day_received += float(AddMoney.objects.filter(date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                
                day_paid = float(Payment.objects.filter(type='out', date=target_date).aggregate(s=Sum('amount'))['s'] or 0)
                day_paid += float(DailyExpense.objects.filter(status='paid', date=target_date).aggregate(s=Sum('total_amount'))['s'] or 0)
                
                running_balance -= (day_received - day_paid)
                
                # 3. Stock Value History (Calculate backwards using StockHistory)
                stock_history_values.append(running_stock_val)
                day_stock_change_val = float(StockHistory.objects.filter(created_at__date=target_date).aggregate(v=Sum(F('quantity_added') * F('product__price'), output_field=DecimalField()))['v'] or 0)
                running_stock_val -= day_stock_change_val
            
            sales_history.reverse()
            expenses_history.reverse()
            balance_history.reverse()
            stock_history_values.reverse()

            # Recents
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
                'total_stock_value': current_stock_val,
                'sales_by_period': sales_by_period,
                'expenses_by_period': expenses_by_period,
                'sales_history': sales_history,
                'expenses_history': expenses_history,
                'balance_history': balance_history,
                'stock_history_values': stock_history_values,
                'recent_employees': recent_employees,
                'recent_invoices': recent_invoices,
                'low_stock_items': low_stock_items,
                'bounced_checks': bounced_checks
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