from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/success/", views.order_success, name="success"),
    path("track/", views.order_track, name="track"),
    path("track/<str:number>/", views.order_track_detail, name="track_detail"),
]
