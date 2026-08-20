from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.marketplace_landing, name="landing"),
    path("goats/", views.marketplace_list, name="list"),
    path("login/", auth_views.LoginView.as_view(template_name="marketplace/login.html", redirect_authenticated_user=True), name="buyer_login"),
    path("register/", views.buyer_register, name="register"),
    path("inquiries/", views.my_inquiries, name="my_inquiries"),
    path("listing/<int:pk>/", views.listing_detail, name="detail"),
    path("listing/<int:pk>/inquire/", views.start_inquiry, name="start_inquiry"),
    path("conversation/<int:pk>/", views.conversation_detail, name="conversation"),
    path("conversation/<int:pk>/reserve/", views.confirm_purchase, name="confirm_purchase"),
    path("reservation/<int:pk>/pickup/", views.pickup_request, name="pickup"),
    path("manage/", views.admin_dashboard, name="admin_dashboard"),
    path("manage/listing/add/", views.manage_listing, name="listing_add"),
    path("manage/listing/<int:pk>/edit/", views.manage_listing, name="listing_edit"),
    path("manage/listing/<int:pk>/publication/", views.set_listing_publication, name="listing_publication"),
    path("manage/inquiries/", views.admin_inquiries, name="admin_inquiries"),
    path("manage/reservation/<int:pk>/action/", views.admin_reservation_action, name="reservation_action"),
    path("manage/sales/", views.sales_history, name="sales_history"),
]
