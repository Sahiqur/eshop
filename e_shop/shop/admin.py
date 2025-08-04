from django.contrib import admin
from .models import Product, Category, Rating, Cart, CartItem, Order, OrderItem

# Register your models here.


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 0
    readonly_fields = ('user', 'rating', 'comment', 'crated_at')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'price',  'stock', 'available', 'created_at', 'updated_at'
    ]
    list_filter = ('available', 'created_at', 'updated_at', 'category')

    list_editable = ('price', 'stock', 'available')
    prepopulated_fields = {'slug': ('name',)}

    inlines = [RatingInline]



class ClassItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
   

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'updated_at']
    inlines= [ClassItemInline]



class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'first_name', 'last_name','email', 'paid', 'created_at', 'status']

    list_filter = ['paid', 'created_at', 'status']
    search_fields = ['first_name', 'last_name', 'email']

    inlines = [OrderItemInline]



@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'product','rating','crated_at']
    list_filter = ['rating', 'crated_at']