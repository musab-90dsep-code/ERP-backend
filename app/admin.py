from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from app.models import (
    Shop, Employee, Attendance, EmployeeTransaction, Contact, 
    ContactEmployee, Product, Invoice, InvoiceItem, Payment, 
    Check, InternalAccount, ProcessingOrder, Order, StockHistory, 
    DailyExpense, AddMoney, UserProfile
)

# ─── User Profile Admin (Inline) ──────────────────────────────────────────────
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profiles'

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
