export interface Store {
  id: string;
  name: string;
  created_at?: string;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  imageUrl: string;
  price: number;
  rating: number | null;
  reviewCount: number;
  category: string;
  brand: string;
  promoText: string | null;
  inStock: boolean;
}

export interface CartItem {
  cart_item_id: string;
  quantity: number;
  added_at: string;
  product: Product;
  available_quantity: number;
  line_total: number;
}

export interface Coupon {
  id: string;
  type: 'frontstore' | 'category' | 'brand';
  discount_details: string;
  category_or_brand: string | null;
  expiration_date: string;
  terms: string | null;
  discount_type: 'percent' | 'fixed' | 'bogo' | 'free_shipping';
  discount_value: number;
  min_purchase_amount: number;
  max_discount: number | null;
  // UI specific
  is_selected?: boolean;
  ineligible_reason?: string;
}

export interface ItemDiscount {
  cart_item_id: string;
  product_name: string;
  coupon_id: string;
  coupon_details: string;
  discount_amount: number;
}

export interface FrontstoreDiscount {
  coupon_id: string;
  coupon_details: string;
  discount_amount: number;
}

export interface CartSummary {
  subtotal: number;
  item_discounts: ItemDiscount[];
  frontstore_discount: FrontstoreDiscount | null;
  discount_total: number;
  final_total: number;
  savings_percentage: number;
}

export interface AppliedCoupon {
  id: string;
  details: string;
  type: string;
}

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  unit_price: number;
  quantity: number;
  discount_amount: number;
  line_total: number;
  applied_coupon: AppliedCoupon | null;
}

export interface Order {
  id: string;
  store: Store;
  items: OrderItem[];
  applied_coupons: {
    item_level: AppliedCoupon[];
    frontstore: AppliedCoupon[];
  };
  totals: {
    subtotal: number;
    item_discounts: number;
    frontstore_discount: number;
    discount_total: number;
    final_total: number;
  };
  status: string;
  created_at: string;
  item_count?: number; // For list view
}
