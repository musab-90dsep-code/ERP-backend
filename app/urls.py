from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
# FileUploadView যদি views.py তে লিখে থাকেন তবে সেটিও ইম্পোর্ট করুন
from app.views import UnifiedAPIView, FileUploadView 

urlpatterns = [
    # আপনার মেইন ইউনিফাইড এন্ডপয়েন্ট
    path('api/', UnifiedAPIView.as_view(), name='unified_api'),
    
    # ইমেজ/ফাইল আপলোডের জন্য এন্ডপয়েন্ট (যা আমরা আগে আলোচনা করেছি)
    path('api/upload/', FileUploadView.as_view(), name='file_upload'),
]

# আপনার হোস্টিং বা লোকাল সার্ভারে ছবিগুলো দেখার জন্য এই অংশটি জরুরি
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)