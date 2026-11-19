from enum import Enum

class UserRole(str, Enum):
    CUSTOMER = "customer"
    RESTAURANT_ADMIN = "restaurant_admin"
    KITCHEN_STAFF = "kitchen_staff"
    DELIVERY_PARTNER = "delivery_partner"
    SUPER_ADMIN = "super_admin"

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentMethod(str, Enum):
    COD = "cod"
    ONLINE = "online"
    CARD = "card"
    UPI = "upi"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"

class InventoryAction(str, Enum):
    STOCK_IN = "stock_in"
    ORDER_DEDUCTION = "order_deduction"
    WASTE_DEDUCTION = "waste_deduction"
    ADJUSTMENT = "adjustment"
