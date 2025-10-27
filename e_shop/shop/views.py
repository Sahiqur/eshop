from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from .models import Product, Category, Rating, Cart, CartItem, Order, OrderItem
from .forms import RegistrationForm, RatingForm, CheckoutForm, ProductSearchForm
from django.db.models import Q, Min, Max, Avg

from django.contrib import messages
from django.contrib.auth.decorators import login_required

from django.views.decorators.csrf import csrf_exempt

from .utils import generate_sslcommerz_payment, send_order_confirmation_email

# Create your views here.

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('shop:profile')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "shop/login.html" )

def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect('shop:profile')
    else:
        form = RegistrationForm()
    return render(request, "shop/register.html", {'form': form})

def logout_view(request):
    logout(request)
    return redirect('shop:login')


def home(request):
    featured_products = Product.objects.filter(available=True).order_by("-created_at")[:8]
    categories = Category.objects.all()

    return render(request, "shop/home.html", {
        "featured_products": featured_products,
        "categories": categories
    })

def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)

    # Filter by category if category_slug is provided
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # Get min and max price for price filtering
    min_price = products.aggregate(Min("price"))["price__min"]
    max_price = products.aggregate(Max("price"))["price__max"]
    
    # Filter by price range
    if request.GET.get("min_price"):
        products = products.filter(price__gte=request.GET.get("min_price"))

    if request.GET.get("max_price"):
        products = products.filter(price__lte=request.GET.get("max_price"))
    
    # Filter by rating
    if request.GET.get("rating"):
        min_rating = request.GET.get("rating")
        products = products.annotate(avg_rating=Avg("ratings__rating")).filter(avg_rating__gte=min_rating)
    
    # Filter by search query
    if request.GET.get("search"):
        query = request.GET.get("search")
        # Filter by name, description, and category name (category.name)
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)  # Correct way to filter ForeignKey field
        )


    return render(request, "shop/product_list.html", {
        "category": category,
        "categories": categories,
         # Use paginated products
        "min_price": min_price,
        "max_price": max_price,
        "products": products
       
    })

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related_product = Product.objects.filter(category = product.category).exclude(id=product.id)
    user_rating = None
    if request.user.is_authenticated:
        try:
            user_rating = Rating.objects.get(product=product, user=request.user)
        except Rating.DoesNotExist:
            pass

        rating_form = RatingForm(instance = user_rating)
        
    return render(request, "shop/product_detail.html", {
        "product": product,
        "related_product": related_product,
        user_rating: user_rating,
        "rating_form": rating_form
    })


@login_required(login_url='/login/')
def cart_detail(request):
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
    
    return render(request, "shop/cart.html", {
        "cart": cart,
    })

@login_required(login_url='/login/')
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
    
    try:
        cart_item = CartItem.objects.get(cart=cart, product=product)
        cart_item.quantity += 1
        cart_item.save()
    except CartItem.DoesNotExist:
        cart_item = CartItem.objects.create(cart=cart, product=product, quantity=1)
    messages.success(request, f"{product.name} has been added to your cart.")
    return redirect('shop:product_detail', slug=product.slug)


@login_required(login_url='/login/')
def cart_remove(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    product = get_object_or_404(Product, id= product_id)
    cart_item = get_object_or_404(CartItem, cart=cart, product=product)
    cart_item.delete()
    messages.success(request, f"{product.name} has been removed from your cart.")
    return redirect('shop:cart_detail')

@login_required(login_url='/login/')
def cart_update(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    product = get_object_or_404(Product, id=product_id)
    cart_item = get_object_or_404(CartItem, cart=cart, product=product)
    
    # Safely convert to int and handle invalid input
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    if quantity <= 0:
        cart_item.delete()
        messages.success(request, f"{product.name} has been removed from your cart.")
    else:
        cart_item.quantity = quantity
        cart_item.save()
        messages.success(request, f"{product.name} has been updated in your cart.")

    return redirect('shop:cart_detail')


@csrf_exempt
@login_required
def checkout(request):
    try:
        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('shop:cart_detail')
    except Cart.DoesNotExist:
        messages.error(request, "You do not have a cart.")
        return redirect('shop:cart_detail')  # removed the extra space

    if request.method == "POST":
        form  = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.save()

            for item in cart.items.all():
                order_item = OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    price=item.product.price,
                    quantity=item.quantity
                )

            cart.items.all().delete()
            request.session['order_id'] = order.id
            return redirect('shop:payment_process')
        else:
            # form is not valid, fall through to GET-style render below
            pass

    # This handles both GET and invalid POST
    initial_data = {}
    if request.user.first_name:
        initial_data["first_name"] = request.user.first_name
    if request.user.last_name:
        initial_data["last_name"] = request.user.last_name
    if request.user.email:
        initial_data["email"] = request.user.email

    form = CheckoutForm(initial=initial_data)
    return render(request, "shop/checkout.html", {
        "cart": cart,
        "form": form
    })


@csrf_exempt
@login_required
def payment_process(request):
    order_id = request.session.get("order_id")
    if not order_id:
        return redirect("shop:home")
    
    order = get_object_or_404(Order, id=order_id)
    payment_data = generate_sslcommerz_payment(order, request)

    if payment_data["status"] == "SUCCESS":
        return redirect(payment_data["GatewayPageURL"])
    else:
        messages.error(request, "Payment failed. Please try again.")
        return redirect("shop:checkout")


@csrf_exempt
@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.paid = True
    order.status = "processing"
    order.transaction_id = order_id
    order.save()

    order_items = order.items.all()
    for item in order_items:
        product = item.product
        product.stock -= item.quantity

        if product.stock <=0:
            product.stock = 0
        product.save()

    send_order_confirmation_email(order)
    messages.success(request, "Your payment was successful.")
    return render(request, 'shop/payment_success.html', {'order': order})


@csrf_exempt
@login_required
def payment_fail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user = request.user)
    order.status = "cancelled"
    order.save()
    messages.error(request, "Your payment failed.")
    return redirect("shop:checkout")

@csrf_exempt
@login_required
def payment_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id, user = request.user)
    order.status = "cancelled"
    order.save()
    messages.error(request, "Your payment was cancelled.")
    return redirect("shop:cart_detail")

@login_required(login_url='/login/')
def profile(request):
    tab = request.GET.get("tab")
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    completed_orders = orders.filter(status = "delivered").count()
    total_spent = sum(order.get_total_cost() for order in orders if order.paid)
    order_history_active = (tab == "orders")

    return render(request, "shop/profile.html", {
        "user": request.user,
        "orders": orders,
        "order_history_active": order_history_active,
        "completed_orders": completed_orders,
        "total_spent": total_spent
    })

@login_required(login_url='/login/')
def rate_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    order_items = OrderItem.objects.filter(
        order__user=request.user,
        order__paid = True,
        product=product
    )

    if not order_items.exists():
        messages.warning(request, "You can only rate a product if you have purchased it.")
        return redirect("shop:product_detail", slug=product.slug)
    try:
        rating = Rating.objects.get(product=product, user=request.user)
    
    except Rating.DoesNotExist:
        rating = None

    if request.method == "POST":
        form  = RatingForm(request.POST, instance = rating)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.product = product
            rating.user = request.user
            rating.save()
            messages.success(request, "Your rating has been submitted.")
            return redirect("shop:product_detail", slug=product.slug)
    else:
        form = RatingForm(instance = rating)

    return render(request, "shop/rate_product.html", {
        "form": form,
        "product": product
        })




def product_search(request):
    form = ProductSearchForm(request.GET)
    products = Product.objects.all()

    if form.is_valid():
        search_query = form.cleaned_data['search']
        if search_query:
            products = products.filter(name__icontains = search_query)

    return render(request, 'shop/product_search.html', {'form': form, 'products': products})
