from django.contrib import admin
from django import forms
from .models import ContactMessage
from .models import (
    GoCart, User, Stop, Route, Schedule, SeatLayout,
    Booking, RouteStop, RouteFare
)

# ✅ Custom Form to filter only drivers in GoCart Admin
class GoCartAdminForm(forms.ModelForm):
    class Meta:
        model = GoCart
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show users with driver role
        self.fields['driver'].queryset = User.objects.filter(role='driver')


# ✅ GoCart Admin
@admin.register(GoCart)
class GoCartAdmin(admin.ModelAdmin):
    form = GoCartAdminForm
    list_display = ('number_plate', 'driver', 'route', 'capacity')
    search_fields = ('number_plate', 'driver__username', 'route__name')
    list_filter = ('route',)


# ✅ Inline RouteStop inside Route Admin
class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1
    fields = ('stop', 'order')
    ordering = ['order']
    sortable_field_name = 'order'


# ✅ Route Admin
@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    inlines = [RouteStopInline]
    list_display = ('name',)
    search_fields = ('name',)


# ✅ RouteFare Admin
@admin.register(RouteFare)
class RouteFareAdmin(admin.ModelAdmin):
    list_display = ('route', 'from_stop', 'to_stop', 'fare')
    search_fields = ('route__name', 'from_stop__name', 'to_stop__name')


# ✅ Stop Admin
@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# ✅ Schedule Admin
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('cart', 'travel_date', 'start_time', 'drop_time')
    list_filter = ('travel_date', 'cart')
    search_fields = ('cart__number_plate',)


# ✅ SeatLayout Admin
@admin.register(SeatLayout)
class SeatLayoutAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'seat_number', 'is_booked')
    list_filter = ('schedule', 'is_booked')
    search_fields = ('seat_number',)


# ✅ Booking Admin
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('student', 'schedule', 'status', 'fare')
    list_filter = ('status', 'schedule__travel_date')
    search_fields = ('student__username', 'schedule__cart__number_plate')

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('name', 'email', 'subject', 'message')

# ✅ User Admin (if you want to customize more, create a UserAdmin later)
admin.site.register(User)