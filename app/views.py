from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import F, Sum, DecimalField, Case, When, Value
from django.utils import timezone
from datetime import timedelta
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    def post(self, request):
        login_input = request.data.get('email', '').strip() 
        password = request.data.get('password', '').strip()
        
        print(f"Login attempt: {login_input}") # DEBUG
        
        # Try finding user by email first (case-insensitive)
        user_obj = User.objects.filter(email__iexact=login_input).first()
        if user_obj:
            username = user_obj.username
        else:
            username = login_input
            
        print(f"Authenticating username: {username}") # DEBUG
        user = authenticate(username=username, password=password)
        print(f"Auth result: {user}") # DEBUG
        
        if user is not None:
            if hasattr(user, 'profile'):
                role = user.profile.role
            elif user.is_superuser:
                role = 'admin'
            else:
                role = 'member'
            
            # Generate or get real DRF token
            token, _ = Token.objects.get_or_create(user=user)
            
            permissions = {}
            if hasattr(user, 'profile'):
                permissions = user.profile.permissions or {}
            elif user.is_superuser:
                # Superusers don't have explicit profile perms usually, or have all. 
                # We can send a flag or empty dict. Backend check handles is_superuser.
                permissions = {"all": True}

            return Response({
                'token': token.key,
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'username': user.username,
                    'role': role,
                    'permissions': permissions
                }
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

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

@method_decorator(csrf_exempt, name='dispatch')
class UnifiedAPIView(APIView):
    """
    A single API endpoint to handle all operations for all models. (Optimized)
    """
    authentication_classes = [TokenAuthentication]
    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        model_name = request.data.get('model')
        obj_id = request.data.get('id')
        data = request.data.get('data', {})
        role = request.data.get('role', 'member')

        shop_id = request.data.get('shop_id')
        
        # ─── Shop ID Validation ───
        if shop_id:
            try:
                import uuid
                uuid.UUID(str(shop_id))
            except ValueError:
                shop_id = None # Ignore invalid UUIDs
        
        if shop_id and model_name != 'shop':
            if isinstance(data, dict):
                data['shop'] = shop_id
            elif data is None:
                data = {'shop': shop_id}

        # ─── Data Cleaning: Handle empty strings for Date/JSON fields ───
        if isinstance(data, dict):
            date_fields = ['dob', 'date', 'issue_date', 'cash_date', 'alert_date', 'transfer_date', 'payment_date', 'customer_since']
            for field in date_fields:
                if field in data and data[field] == '':
                    data[field] = None

            # Handle empty strings for numeric fields
            numeric_fields = ['salary', 'daily_allowance', 'monthly_allowance', 'amount', 'total', 'subtotal', 'discount', 'paid_amount', 'due_amount', 'opening_balance', 'credit_limit', 'discount_percent']
            for field in numeric_fields:
                if field in data and data[field] == '':
                    data[field] = None

        if not action:
            return Response({'error': 'Missing "action" in request payload.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # ========================================================
        # 🛡️ SECURITY: SERVER-SIDE PERMISSION CHECK
        # ========================================================
        if action in ['create', 'update', 'delete', 'bulk_delete']:
            db_user = request.user
            token_was_sent = False

            print(f"[PERM DEBUG] action={action}, model={model_name}, drf_user={db_user}, is_auth={getattr(db_user, 'is_authenticated', False)}")

            # If DRF didn't authenticate, manually parse token from header
            if not db_user or not db_user.is_authenticated:
                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                print(f"[PERM DEBUG] Auth header: {auth_header[:50] if auth_header else 'NONE'}")
                # Handle both 'Token xxx' and 'Bearer xxx' formats
                if auth_header.startswith('Token ') or auth_header.startswith('Bearer '):
                    token_was_sent = True
                    raw_token = auth_header.split(' ', 1)[1].strip()
                    try:
                        from rest_framework.authtoken.models import Token as AuthToken
                        token_obj = AuthToken.objects.select_related('user').get(key=raw_token)
                        db_user = token_obj.user
                        print(f"[PERM DEBUG] Manual token resolved user: {db_user}")
                    except Exception as e:
                        db_user = None
                        print(f"[PERM DEBUG] Token lookup failed: {e}")

            # If a token was sent but is INVALID -> force re-login
            if token_was_sent and (not db_user or not db_user.is_authenticated):
                return Response(
                    {'error': 'Invalid or expired token. Please sign out and log in again.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Perform permission check with identified user
            if db_user and db_user.is_authenticated:
                print(f"[PERM DEBUG] User identified: {db_user.username}, superuser={db_user.is_superuser}")
                if db_user.is_superuser:
                    print("[PERM DEBUG] Superuser - full access granted")
                elif hasattr(db_user, 'profile'):
                    profile = db_user.profile
                    db_role = profile.role
                    db_permissions = profile.permissions or {}
                    print(f"[PERM DEBUG] Role={db_role}, Permissions={db_permissions}")

                    if db_role == 'admin':
                        print("[PERM DEBUG] Admin role - full access")
                    elif db_role == 'member':
                        return Response(
                            {'error': 'Permission Denied: Members can only view data.'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    elif db_role == 'manager':
                        model_to_module = {
                            'product': 'inventory', 'stock_history': 'inventory',
                            'invoice': 'sales', 'payment': 'sales', 'contact': 'sales',
                            'employee': 'employees', 
                            'attendance': 'attendance_payroll', 
                            'employee_transaction': 'attendance_payroll',
                            'processing_order': 'processing', 'order': 'processing',
                            'daily_expense': 'expenses',
                            'add_money': 'finance', 'internal_account': 'finance',
                            'shop': 'settings',
                        }
                        module = model_to_module.get(model_name or '')
                        print(f"[PERM DEBUG] module={module}, module_perms={db_permissions.get(module, [])}")
                        if module:
                            module_perms = db_permissions.get(module, [])
                            action_to_perm = {
                                'create': 'add',
                                'update': 'edit',
                                'bulk_delete': 'delete',
                                'delete': 'delete',
                            }
                            required_perm = action_to_perm.get(action)
                            print(f"[PERM DEBUG] required_perm={required_perm}, has_perm={'YES' if required_perm in module_perms else 'NO'}")
                            if required_perm and required_perm not in module_perms:
                                return Response(
                                    {'error': f'Permission Denied: You do not have "{required_perm}" permission for {module}.'},
                                    status=status.HTTP_403_FORBIDDEN
                                )
            else:
                print("[PERM DEBUG] No authenticated user found - skipping permission check")

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
            
            # Total Customer Due Calculation (summing all customer dues matching ContactSerializer logic)
            customers_qs = Contact.objects.filter(type__in=['customer', 'processor'], **({'shop_id': shop_id} if shop_id else {}))
            total_due = 0.0
            for cust in customers_qs:
                total_invoiced = float(Invoice.objects.filter(
                    contact=cust, type__in=['sell', 'exchange']
                ).aggregate(s=Sum('total'))['s'] or 0)

                total_returned = float(Invoice.objects.filter(
                    contact=cust, type='return'
                ).aggregate(s=Sum('total'))['s'] or 0)

                total_received = float(Payment.objects.filter(
                    contact=cust, type='in'
                ).aggregate(s=Sum('amount'))['s'] or 0)

                total_refunded = float(Payment.objects.filter(
                    contact=cust, type='out'
                ).aggregate(s=Sum('amount'))['s'] or 0)

                total_due += (total_invoiced - total_returned) - (total_received - total_refunded)

            # Stock Value Calculation
            products_qs = Product.objects.filter(**({'shop_id': shop_id} if shop_id else {}))
            current_stock_val = 0.0
            for prod in products_qs:
                if prod.variants and isinstance(prod.variants, list) and len(prod.variants) > 0:
                    for variant in prod.variants:
                        if isinstance(variant, dict):
                            v_stock = float(variant.get('stock') or 0)
                            v_price = float(variant.get('price') or 0)
                            current_stock_val += v_stock * v_price
                else:
                    prod_stock = float(prod.stock_quantity or 0)
                    prod_price = float(prod.price or 0)
                    current_stock_val += prod_stock * prod_price
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
                # --- Shop Limit Protection ---
                if model_name == 'shop':
                    if Shop.objects.count() >= 3:
                        return Response({
                            'error': 'Shop limit reached. You can only create a maximum of 3 shops.'
                        }, status=status.HTTP_400_BAD_REQUEST)

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
                
                # Ensure obj_id is a clean string (prevents some UUID lookup issues)
                clean_id = str(obj_id).strip()
                
                try:
                    obj = ModelClass.objects.get(id=clean_id)
                    if model_name == 'invoice':
                        restock = True
                        if isinstance(data, dict) and 'restock' in data:
                            # if it comes as boolean or string
                            r_val = data.get('restock')
                            if str(r_val).lower() == 'false':
                                restock = False
                        obj.delete(restock=restock)
                    else:
                        obj.delete()
                    return Response({'message': f'{model_name.capitalize()} deleted successfully.'}, status=status.HTTP_200_OK)
                except ModelClass.DoesNotExist:
                    return Response({'error': f'No {model_name} found with ID: {clean_id}'}, status=status.HTTP_404_NOT_FOUND)
                except Exception as e:
                    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 6. BULK DELETE
            elif action == 'bulk_delete':
                if isinstance(data, dict) and data:
                    queryset = ModelClass.objects.filter(**data)
                    count = queryset.count()
                    queryset.delete()
                    return Response({"deleted": count}, status=status.HTTP_200_OK)
                return Response({"error": "No filters provided for bulk delete"}, status=status.HTTP_400_BAD_REQUEST)

            # 7. SPECIAL: PROCESSING BALANCES (Optimized & Matched to Frontend)
            elif action == 'balances' and model_name == 'processing_order':
                shop_filter = {'shop_id': shop_id} if shop_id else {}
                
                # Step 1: Get all processors
                processors = Contact.objects.filter(type='processor', **shop_filter)
                processor_map = {str(p.id): {
                    'processor': str(p.id),
                    'processor_name': p.name or p.shop_name or 'Unknown Processor',
                    'processor_shop': p.shop_name,
                    'has_data': False,
                    'rows': []
                } for p in processors}

                # Step 2: Get aggregated data
                results = ProcessingOrder.objects.filter(**shop_filter).values(
                    'processor__id',
                    'processor__name', 
                    'processor__shop_name', 
                    'product__name',
                    'product__unit'
                ).annotate(
                    total_issued_quantity=Sum(Case(When(type='issued', then=F('quantity')), default=Value(0), output_field=DecimalField())),
                    total_received_quantity=Sum(Case(When(type='received', then=F('quantity')), default=Value(0), output_field=DecimalField())),
                    total_issued_value=Sum(Case(When(type='issued', then=F('quantity') * Case(When(process_type='auto', then=F('product__processing_price_auto')), default=F('product__processing_price_manual'), output_field=DecimalField())), default=Value(0), output_field=DecimalField())),
                    total_received_value=Sum(Case(When(type='received', then=F('quantity') * Case(When(process_type='auto', then=F('product__processing_price_auto')), default=F('product__processing_price_manual'), output_field=DecimalField())), default=Value(0), output_field=DecimalField())),
                ).annotate(
                    total_outstanding_quantity=F('total_issued_quantity') - F('total_received_quantity'),
                    total_outstanding_value=F('total_issued_value') - F('total_received_value')
                ).order_by('processor__name')

                # Step 3: Merge data
                for r in results:
                    pid = str(r['processor__id'])
                    if pid in processor_map:
                        processor_map[pid]['has_data'] = True
                        processor_map[pid]['rows'].append({
                            'processor': pid,
                            'processor_name': r['processor__name'] or r['processor__shop_name'] or 'Unknown Processor',
                            'processor_shop': r['processor__shop_name'],
                            'product_name': r['product__name'],
                            'unit': r['product__unit'],
                            'total_issued_quantity': float(r['total_issued_quantity'] or 0),
                            'total_issued_value': float(r['total_issued_value'] or 0),
                            'total_received_quantity': float(r['total_received_quantity'] or 0),
                            'total_received_value': float(r['total_received_value'] or 0),
                            'total_outstanding_quantity': float(r['total_outstanding_quantity'] or 0),
                            'total_outstanding_value': float(r['total_outstanding_value'] or 0)
                        })

                clean_results = []
                for pid, pdata in processor_map.items():
                    if pdata['has_data']:
                        clean_results.extend(pdata['rows'])
                    else:
                        # Add a default row for processors with no orders
                        clean_results.append({
                            'processor': pid,
                            'processor_name': pdata['processor_name'],
                            'processor_shop': pdata['processor_shop'],
                            'product_name': 'No Items',
                            'unit': '-',
                            'total_issued_quantity': 0,
                            'total_issued_value': 0,
                            'total_received_quantity': 0,
                            'total_received_value': 0,
                            'total_outstanding_quantity': 0,
                            'total_outstanding_value': 0
                        })

                return Response(clean_results)

            # 8. SPECIAL: CONTACT DUE BALANCE
            elif action == 'due' and model_name == 'contact':
                if not obj_id:
                    return Response({'error': 'Missing "id" for contact due.'}, status=status.HTTP_400_BAD_REQUEST)

                # 'data' is the nested sub-object from frontend: { type: 'customer' | 'supplier' }
                contact_type = data.get('type', 'customer') if isinstance(data, dict) else 'customer'
                shop_filter = {'shop_id': shop_id} if shop_id else {}

                if contact_type == 'customer' or contact_type == 'in':
                    # All money owed by customer = total of sell + exchange invoices
                    total_invoiced = float(Invoice.objects.filter(
                        contact_id=obj_id, type__in=['sell', 'exchange'], **shop_filter
                    ).aggregate(s=Sum('total'))['s'] or 0)

                    # Credit customer for returns
                    total_returned = float(Invoice.objects.filter(
                        contact_id=obj_id, type='return', **shop_filter
                    ).aggregate(s=Sum('total'))['s'] or 0)

                    # All payments received from this customer
                    total_received = float(Payment.objects.filter(
                        contact_id=obj_id, type='in', **shop_filter
                    ).aggregate(s=Sum('amount'))['s'] or 0)

                    # All refunds given back to customer
                    total_refunded = float(Payment.objects.filter(
                        contact_id=obj_id, type='out', **shop_filter
                    ).aggregate(s=Sum('amount'))['s'] or 0)

                    # Net Due = (What they owe us - Returns) - (What they paid - Refunds given)
                    due = (total_invoiced - total_returned) - (total_received - total_refunded)

                else:  # supplier or out
                    # All money we owe supplier = total of buy invoices
                    total_purchased = float(Invoice.objects.filter(
                        contact_id=obj_id, type='buy', **shop_filter
                    ).aggregate(s=Sum('total'))['s'] or 0)

                    # Credit for buy returns
                    total_buy_returns = float(Invoice.objects.filter(
                        contact_id=obj_id, type='return', **shop_filter
                    ).aggregate(s=Sum('total'))['s'] or 0)

                    # All payments we made to supplier
                    total_paid_out = float(Payment.objects.filter(
                        contact_id=obj_id, type='out', **shop_filter
                    ).aggregate(s=Sum('amount'))['s'] or 0)

                    # Any money received back from supplier
                    total_received_back = float(Payment.objects.filter(
                        contact_id=obj_id, type='in', **shop_filter
                    ).aggregate(s=Sum('amount'))['s'] or 0)

                    # Net Due = (What we owe - Returns) - (What we already paid - Received back)
                    due = (total_purchased - total_buy_returns) - (total_paid_out - total_received_back)

                due = round(due, 2)
                return Response({'due': due}, status=status.HTTP_200_OK)

            else:
                return Response({'error': f'Action "{action}" not supported.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            return Response({'error': str(e), 'trace': traceback.format_exc()}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class FileUploadView(APIView):
    """
    Endpoint for uploading images/files to local media storage.
    """
    def post(self, request, *args, **kwargs):
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({'error': 'No file provided in the request.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Ensure media directory exists
            if not os.path.exists(settings.MEDIA_ROOT):
                os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
                
            file_name = default_storage.save(file.name, ContentFile(file.read()))
            
            # Generate absolute URL - prioritize HTTPS if configured
            file_url = request.build_absolute_uri(f'/media/{file_name}')
            if 'https' not in file_url and request.is_secure():
                 file_url = file_url.replace('http://', 'https://')
            
            return Response({'url': file_url}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)