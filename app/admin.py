from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from app.models import (
    Shop, Employee, Attendance, EmployeeTransaction, Contact, 
    ContactEmployee, Product, Invoice, InvoiceItem, Payment, 
    Check, InternalAccount, ProcessingOrder, Order, StockHistory, 
    DailyExpense, AddMoney, UserProfile
)

from django import forms

# ─── Permission Config ────────────────────────────────────────────────────────
MODULES = ['inventory', 'sales', 'purchase', 'processing', 'employees', 'attendance_payroll', 'expenses', 'finance', 'settings']
ACTIONS = ['add', 'edit', 'delete']

# ─── Custom Form with Statically Declared Fields ──────────────────────────────
class UserProfileForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    
    # ... other fields ...
    perm_inventory_add = forms.BooleanField(required=False, label='Add')
    perm_inventory_edit = forms.BooleanField(required=False, label='Edit')
    perm_inventory_delete = forms.BooleanField(required=False, label='Delete')
    perm_sales_add = forms.BooleanField(required=False, label='Add')
    perm_sales_edit = forms.BooleanField(required=False, label='Edit')
    perm_sales_delete = forms.BooleanField(required=False, label='Delete')
    perm_purchase_add = forms.BooleanField(required=False, label='Add')
    perm_purchase_edit = forms.BooleanField(required=False, label='Edit')
    perm_purchase_delete = forms.BooleanField(required=False, label='Delete')
    perm_processing_add = forms.BooleanField(required=False, label='Add')
    perm_processing_edit = forms.BooleanField(required=False, label='Edit')
    perm_processing_delete = forms.BooleanField(required=False, label='Delete')
    # Split Employees
    perm_employees_add = forms.BooleanField(required=False, label='Add')
    perm_employees_edit = forms.BooleanField(required=False, label='Edit')
    perm_employees_delete = forms.BooleanField(required=False, label='Delete')
    # Attendance & Payroll
    perm_attendance_payroll_add = forms.BooleanField(required=False, label='Add')
    perm_attendance_payroll_edit = forms.BooleanField(required=False, label='Edit')
    perm_attendance_payroll_delete = forms.BooleanField(required=False, label='Delete')

    perm_expenses_add = forms.BooleanField(required=False, label='Add')
    perm_expenses_edit = forms.BooleanField(required=False, label='Edit')
    perm_expenses_delete = forms.BooleanField(required=False, label='Delete')
    perm_finance_add = forms.BooleanField(required=False, label='Add')
    perm_finance_edit = forms.BooleanField(required=False, label='Edit')
    perm_finance_delete = forms.BooleanField(required=False, label='Delete')
    perm_settings_add = forms.BooleanField(required=False, label='Add')
    perm_settings_edit = forms.BooleanField(required=False, label='Edit')
    perm_settings_delete = forms.BooleanField(required=False, label='Delete')

    class Meta:
        model = UserProfile
        fields = ['role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            perms = self.instance.permissions or {}
            for mod in MODULES:
                for act in ACTIONS:
                    field_name = f'perm_{mod}_{act}'
                    if field_name in self.fields:
                        self.initial[field_name] = act in perms.get(mod, [])

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_perms = {}
        for mod in MODULES:
            mod_acts = [act for act in ACTIONS if self.cleaned_data.get(f'perm_{mod}_{act}')]
            if mod_acts:
                new_perms[mod] = mod_acts
        instance.permissions = new_perms
        if commit:
            instance.save()
        return instance

# ─── User Profile Admin (Inline) ──────────────────────────────────────────────
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    form = UserProfileForm
    can_delete = False
    extra = 1
    max_num = 1
    verbose_name_plural = 'User Permissions'
    
    fieldsets = [
        ('Role Settings', {'fields': ['role']}),
        ('Inventory (Products & Stock)', {'fields': [('perm_inventory_add', 'perm_inventory_edit', 'perm_inventory_delete')]}),
        ('Sales (Invoices & Payments)', {'fields': [('perm_sales_add', 'perm_sales_edit', 'perm_sales_delete')]}),
        ('Purchase (Suppliers)', {'fields': [('perm_purchase_add', 'perm_purchase_edit', 'perm_purchase_delete')]}),
        ('Processing (Production)', {'fields': [('perm_processing_add', 'perm_processing_edit', 'perm_processing_delete')]}),
        ('Staff Management (Add/Edit Employees)', {'fields': [('perm_employees_add', 'perm_employees_edit', 'perm_employees_delete')]}),
        ('Attendance & Payroll (Daily Ops)', {'fields': [('perm_attendance_payroll_add', 'perm_attendance_payroll_edit', 'perm_attendance_payroll_delete')]}),
        ('Expenses', {'fields': [('perm_expenses_add', 'perm_expenses_edit', 'perm_expenses_delete')]}),
        ('Finance & Accounts', {'fields': [('perm_finance_add', 'perm_finance_edit', 'perm_finance_delete')]}),
        ('Settings (Shop)', {'fields': [('perm_settings_add', 'perm_settings_edit', 'perm_settings_delete')]}),
    ]

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Register other models
admin.site.register(Shop)
admin.site.register(Employee)
admin.site.register(Attendance)
admin.site.register(EmployeeTransaction)
admin.site.register(Contact)
admin.site.register(ContactEmployee)
admin.site.register(Product)
admin.site.register(Invoice)
admin.site.register(InvoiceItem)
admin.site.register(Payment)
admin.site.register(Check)
admin.site.register(InternalAccount)
admin.site.register(ProcessingOrder)
admin.site.register(Order)
admin.site.register(StockHistory)
admin.site.register(DailyExpense)
admin.site.register(AddMoney)
