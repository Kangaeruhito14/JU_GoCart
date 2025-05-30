from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class Stop(models.Model):
    name = models.CharField(max_length=100)
    lat = models.FloatField()
    lng = models.FloatField()

    def __str__(self):
        return self.name

class Route(models.Model):
    name = models.CharField(max_length=100)
    stops = models.ManyToManyField('Stop', through='RouteStop')

    def __str__(self):
        return self.name

class RouteStop(models.Model):
    route = models.ForeignKey('Route', on_delete=models.CASCADE)
    stop = models.ForeignKey('Stop', on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.route.name} - {self.stop.name} (#{self.order})"

class RouteFare(models.Model):
    route = models.ForeignKey('Route', on_delete=models.CASCADE)
    from_stop = models.ForeignKey('Stop', related_name='from_stop_fares', on_delete=models.CASCADE)
    to_stop = models.ForeignKey('Stop', related_name='to_stop_fares', on_delete=models.CASCADE)
    fare = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.from_stop} to {self.to_stop} fare: {self.fare}"

class GoCart(models.Model):
    number_plate = models.CharField(max_length=50)
    driver = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'driver'})
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    capacity = models.IntegerField()

    def __str__(self):
        return f"Cart {self.number_plate}"

class Schedule(models.Model):
    cart = models.ForeignKey(GoCart, on_delete=models.CASCADE)
    travel_date = models.DateField()
    start_time = models.TimeField()
    drop_time = models.TimeField()

    def __str__(self):
        return f"{self.cart} on {self.travel_date}"

class SeatLayout(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=5)
    is_booked = models.BooleanField(default=False)
    booked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

class Booking(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    seats = models.ManyToManyField(SeatLayout)
    from_stop = models.ForeignKey(Stop, related_name='from_bookings', on_delete=models.CASCADE)
    to_stop = models.ForeignKey(Stop, related_name='to_bookings', on_delete=models.CASCADE)
    fare = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')])
    payment_id = models.CharField(max_length=100, null=True, blank=True)
    ticket_url = models.URLField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking by {self.student} for {self.schedule}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    replied = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.name} ({self.email})"