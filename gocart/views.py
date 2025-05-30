from datetime import datetime
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db.models import Prefetch
from .models import Route, Stop, Schedule, Booking, GoCart, SeatLayout, RouteStop, RouteFare, ContactMessage
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
import pdfkit

# -------------------------
# Profile Views
# -------------------------

@login_required
def ride_history(request):
    user = request.user

    if user.role == 'student':
        bookings = (
            Booking.objects.filter(student=user)
            .select_related('schedule__cart__route', 'from_stop', 'to_stop')
            .prefetch_related('seats')
        )

        enriched_bookings = []
        for booking in bookings:
            seat_numbers = [seat.seat_number for seat in booking.seats.all()]
            route = booking.schedule.cart.route

            route_stops = list(
                RouteStop.objects.filter(route=route)
                .select_related('stop')
                .order_by('order')
            )

            # Determine from/to indices and path
            try:
                from_idx = next(i for i, rs in enumerate(route_stops) if rs.stop == booking.from_stop)
                to_idx = next(i for i, rs in enumerate(route_stops) if rs.stop == booking.to_stop)
                path = [rs.stop.name for rs in route_stops[from_idx:to_idx + 1]] if from_idx < to_idx else []
            except StopIteration:
                path = []

            enriched_bookings.append({
                'booking': booking,
                'seat_booking_details': seat_numbers,
                'path': path,
            })

        return render(request, 'gocart/ride_history.html', {
            'enriched_bookings': enriched_bookings
        })

    elif user.role == 'driver':
        carts = GoCart.objects.filter(driver=user)
        schedules = (
            Schedule.objects.filter(cart__in=carts)
            .select_related('cart__route')
            .prefetch_related(
                Prefetch('seatlayout_set', queryset=SeatLayout.objects.select_related('booked_by')),
                Prefetch(
                    'booking_set',
                    queryset=Booking.objects.select_related('student', 'from_stop', 'to_stop')
                                        .prefetch_related('seats')
            )
        )
    )

    enriched_schedules = []

    for schedule in schedules:
        route = schedule.cart.route

        # Get full route path
        route_stops = (
            RouteStop.objects.filter(route=route)
            .select_related('stop')
            .order_by('order')
        )
        full_path = [rs.stop.name for rs in route_stops]

        enriched_schedules.append({
            'schedule': schedule,
            'route_path': full_path,
        })

    return render(request, 'gocart/ride_history_driver.html', {
        'schedules': enriched_schedules
    })


@login_required
def trip_details_json(request, trip_id):
    if request.user.role != 'driver':
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    bookings = (
        Booking.objects.filter(schedule_id=trip_id, status__in=['confirmed', 'cancelled'])
        .select_related('student', 'from_stop', 'to_stop', 'schedule__cart__route')
        .prefetch_related('seats')
    )

    data = {
        'bookings': []
    }

    for b in bookings:
        seat_numbers = [seat.seat_number for seat in b.seats.all()]
        route = b.schedule.cart.route

        route_stops = list(
            RouteStop.objects.filter(route=route)
            .select_related('stop')
            .order_by('order')
        )

        # Dynamically determine path
        try:
            from_idx = next(i for i, rs in enumerate(route_stops) if rs.stop == b.from_stop)
            to_idx = next(i for i, rs in enumerate(route_stops) if rs.stop == b.to_stop)
            path = [rs.stop.name for rs in route_stops[from_idx:to_idx + 1]] if from_idx < to_idx else []
        except StopIteration:
            path = []

        booking_info = {
            'seat_numbers': seat_numbers,
            'username': b.student.username if b.student else "N/A",
            'from': b.from_stop.name if b.from_stop else "N/A",
            'to': b.to_stop.name if b.to_stop else "N/A",
            'booking_time': b.created_at.strftime('%Y-%m-%d %H:%M:%S') if b.created_at else "Unknown",
            'status': b.status.capitalize() if b.status in ['confirmed', 'cancelled'] else None,
            'path': path,
        }
        data['bookings'].append(booking_info)

    return JsonResponse(data)

# -------------------------
# Cart Search & Results
# -------------------------

def search_carts(request):
    if request.method == 'POST':
        from_stop_value = request.POST.get('from')
        to_stop_value = request.POST.get('to')
        input_date_str = request.POST.get('travel_date')

        try:
            travel_date = datetime.strptime(input_date_str, "%Y-%m-%d").date()
            now = datetime.now()
            today, current_time = now.date(), now.time()

            from_stop = Stop.objects.get(name=from_stop_value)
            to_stop = Stop.objects.get(name=to_stop_value)

            # ✅ Save selected stop IDs in session so confirm_booking can access them
            request.session['from_stop_id'] = from_stop.id
            request.session['to_stop_id'] = to_stop.id

            possible_routes = Route.objects.filter(routestop__stop=from_stop).distinct()
            matched_routes = []

            for route in possible_routes:
                stops = list(RouteStop.objects.filter(route=route).order_by('order').values_list('stop_id', flat=True))
                if from_stop.id in stops and to_stop.id in stops and stops.index(from_stop.id) < stops.index(to_stop.id):
                    matched_routes.append(route)

            schedule_filter = {
                'travel_date': travel_date,
                'cart__route__in': matched_routes
            }
            if travel_date == today:
                schedule_filter['start_time__gt'] = current_time

            schedules = Schedule.objects.filter(**schedule_filter).select_related('cart', 'cart__route').order_by('travel_date', 'start_time')

            return render(request, 'gocart/search_results.html', {
                'schedules': schedules,
                'from_stop': from_stop,
                'to_stop': to_stop,
                'travel_date': travel_date
            })

        except (Stop.DoesNotExist, ValueError):
            # messages.error(request, "Invalid stop name or date format.")
            return redirect('search_carts_page')

    return redirect('home')

# -------------------------
# Cart Detail & Booking
# -------------------------


def cart_detail(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    seat_layout = SeatLayout.objects.filter(schedule=schedule)
    booked_seats = seat_layout.filter(is_booked=True).values_list('seat_number', flat=True)

    return render(request, 'gocart/cart_detail.html', {
        'schedule': schedule,
        'cart': schedule.cart,
        'seats': seat_layout,
        'booked_seats': list(booked_seats),
    })



def track_location(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    route_stops = RouteStop.objects.filter(route=schedule.cart.route).order_by('order')
    return render(request, 'gocart/track_location.html', {
        'schedule': schedule,
        'route_stops': route_stops,
    })

@login_required
def book_seat(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)

    if request.method == 'POST':
        seat_ids_string = request.POST.get('selected_seats', '')
        seat_ids = [int(seat_id) for seat_id in seat_ids_string.split(',') if seat_id.strip()]

        selected_seats = SeatLayout.objects.filter(id__in=seat_ids)

        for seat in selected_seats:
            if seat.is_booked:
                messages.error(request, f'Seat {seat.seat_number} is already booked.')
                return redirect('cart_detail', schedule_id=schedule_id)

        request.session['selected_seat_ids'] = seat_ids
        # messages.success(request, 'Seats selected successfully! Proceed to booking confirmation.')

        return redirect('confirm_booking', schedule_id=schedule_id)

    return redirect('cart_detail', schedule_id=schedule_id)


@login_required
def confirm_booking(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    cart = schedule.cart
    selected_seat_ids = request.session.get('selected_seat_ids', [])

    # Get from_stop & to_stop from session
    from_stop_id = request.session.get('from_stop_id')
    to_stop_id = request.session.get('to_stop_id')
    from_stop = get_object_or_404(Stop, id=from_stop_id) if from_stop_id else None
    to_stop = get_object_or_404(Stop, id=to_stop_id) if to_stop_id else None

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')

        if not selected_seat_ids:
            # messages.error(request, 'No seats selected.')
            return redirect('cart_detail', schedule_id=schedule_id)

        selected_seats = SeatLayout.objects.filter(id__in=selected_seat_ids)

        total_fare = calculate_fare(cart.route, from_stop, to_stop) * len(selected_seat_ids)

        booking = Booking.objects.create(
            student=request.user,
            schedule=schedule,
            from_stop=from_stop,
            to_stop=to_stop,
            fare=total_fare,
            status='pending'
        )
        booking.seats.set(selected_seats)
        booking.save()

        request.session['payment_method'] = payment_method
        del request.session['selected_seat_ids']

        return redirect('payment_page', booking_id=booking.id)

    total_fare = calculate_fare(cart.route, from_stop, to_stop) * len(selected_seat_ids) if selected_seat_ids else None

    return render(request, 'gocart/confirm_booking.html', {
        'cart': cart,
        'schedule': schedule,
        'from_stop': from_stop,
        'to_stop': to_stop,
        'total_fare': total_fare
    })


def calculate_fare(route, from_stop, to_stop):
    total_fare = 0
    route_stops = list(RouteStop.objects.filter(route=route).order_by('order'))

    try:
        from_index = next(i for i, stop in enumerate(route_stops) if stop.stop == from_stop)
        to_index = next(i for i, stop in enumerate(route_stops) if stop.stop == to_stop)
    except StopIteration:
        return 0  # One of the stops not found in the route

    if from_index < to_index:
        for i in range(from_index, to_index):
            try:
                route_fare = RouteFare.objects.get(
                    route=route,
                    from_stop=route_stops[i].stop,
                    to_stop=route_stops[i + 1].stop
                )
                total_fare += route_fare.fare
            except RouteFare.DoesNotExist:
                continue  # Skip if fare not defined between two stops

    return total_fare


@login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method not in ['bkash', 'nagad', 'rocket']:
            # messages.error(request, 'Invalid payment method.')
            return redirect('payment_page', booking_id=booking.id)

        booking.status = 'confirmed'
        booking.payment_id = payment_method
        booking.save()

        for seat in booking.seats.all():
            seat.is_booked = True
            seat.save()

        messages.success(request, 'Payment successful!')
        return redirect('download_ticket', booking_id=booking.id)

    # 🟢 Pre-select method from session if booking.payment_id is not yet set
    selected_method = booking.payment_id or request.session.get('payment_method')

    return render(request, 'gocart/payment_page.html', {
        'booking': booking,
        'selected_method': selected_method
    })


# -------------------------
# Ticket PDF
# -------------------------

@login_required
def show_ticket_details(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'gocart/ticket_download.html', {'booking': booking})

# PDF download
@login_required
def download_ticket_pdf(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    template = get_template('gocart/ticket_template.html')  # Must be standalone HTML
    html = template.render({'booking': booking})
    options = getattr(settings, 'PDFKIT_OPTIONS', {})

    pdf = pdfkit.from_string(html, False, options=options)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ticket_{booking.id}.pdf"'
    return response

# -------------------------
# Driver Management Views
# -------------------------

@login_required
def driver_trip_detail(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)

    seats = SeatLayout.objects.filter(schedule=schedule).order_by('seat_number')
    bookings = Booking.objects.filter(schedule=schedule).prefetch_related('seats', 'student')

    seat_to_booking = {}
    user_seat_counts = defaultdict(list)

    for booking in bookings:
        for seat in booking.seats.all():
            seat_to_booking[seat.id] = booking
            user_seat_counts[booking.student.username].append(seat.id)

    return render(request, 'gocart/driver_trip_detail.html', {
        'schedule': schedule,
        'seats': seats,
        'seat_to_booking': seat_to_booking,
        'user_seats': user_seat_counts
    })
