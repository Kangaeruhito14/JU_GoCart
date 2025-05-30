from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [

    # Profile
    path('ride-history/', views.ride_history, name='ride_history'),

    # Search and Booking
    path('search/', views.search_carts, name='search_carts'),
    path('track/<int:schedule_id>/', views.track_location, name='track_location'),
    path('schedule/<int:schedule_id>/', views.cart_detail, name='cart_detail'),
    path('schedule/<int:schedule_id>/book/', views.book_seat, name='book_seat'),
    path('schedule/<int:schedule_id>/confirm/', views.confirm_booking, name='confirm_booking'),

    # Payment
    path('payment/<int:booking_id>/', views.payment_page, name='payment_page'),
    path('ticket/<int:booking_id>/', views.show_ticket_details, name='download_ticket'),
    path('ticket/<int:booking_id>/pdf/', views.download_ticket_pdf, name='download_ticket_pdf'),


    # Driver Management
    path('driver/trips/<int:schedule_id>/', views.driver_trip_detail, name='driver_trip_detail'),
    path('driver/trip-details/<int:trip_id>/json/', views.trip_details_json, name='trip_details_json'),

]