-- ============================================================================
-- Migration 002: Retail Cart & Checkout Schema
-- MultiModal AI Retail App - Full Shopping Experience
-- Run after postgres_schema.sql
-- ============================================================================

-- ============================================================================
-- D-1: STORES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- D-3: STORE INVENTORY TABLE
-- Links stores to products with quantity tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS store_inventory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 20 CHECK (quantity >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(store_id, product_id)
);

-- ============================================================================
-- D-4: ALTER COUPONS TABLE
-- Add structured fields for programmatic discount calculation
-- ============================================================================
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS discount_type VARCHAR(20)
    CHECK (discount_type IN ('percent', 'fixed', 'bogo', 'free_shipping'));
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS discount_value DECIMAL(10, 2);
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS min_purchase_amount DECIMAL(10, 2) DEFAULT 0;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS max_discount DECIMAL(10, 2);
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;

-- ============================================================================
-- D-5: CART ITEMS TABLE
-- User shopping cart with quantity
-- ============================================================================
CREATE TABLE IF NOT EXISTS cart_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, store_id, product_id)
);

-- ============================================================================
-- D-6: CART COUPONS TABLE
-- User-selected coupons for their cart
-- ============================================================================
CREATE TABLE IF NOT EXISTS cart_coupons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, coupon_id)
);

-- ============================================================================
-- D-7: ORDERS TABLE
-- Completed purchases
-- ============================================================================
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE RESTRICT,
    subtotal DECIMAL(10, 2) NOT NULL,
    discount_total DECIMAL(10, 2) NOT NULL DEFAULT 0,
    final_total DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'completed'
        CHECK (status IN ('pending', 'completed', 'cancelled', 'refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- D-8: ORDER ITEMS TABLE
-- Individual items in each order with applied discounts
-- ============================================================================
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    product_name VARCHAR(255) NOT NULL,  -- Snapshot at time of purchase
    product_price DECIMAL(10, 2) NOT NULL,  -- Snapshot at time of purchase
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    applied_coupon_id UUID REFERENCES coupons(id) ON DELETE SET NULL,
    discount_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
    line_total DECIMAL(10, 2) NOT NULL,  -- (price * quantity) - discount
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- D-9: COUPON INTERACTIONS TABLE
-- Track user interactions with coupons for analytics
-- ============================================================================
CREATE TABLE IF NOT EXISTS coupon_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL
        CHECK (action IN ('added_to_cart', 'removed_from_cart', 'applied', 'redeemed')),
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- D-10: USER PREFERENCES TABLE
-- Store user settings including selected store
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    selected_store_id UUID REFERENCES stores(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- D-11: ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on new tables
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE store_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE cart_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE cart_coupons ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE coupon_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Stores: Everyone can read
CREATE POLICY stores_select_policy ON stores FOR SELECT USING (true);

-- Store Inventory: Everyone can read
CREATE POLICY store_inventory_select_policy ON store_inventory FOR SELECT USING (true);

-- Cart Items: Users can only access their own cart
CREATE POLICY cart_items_select_policy ON cart_items
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY cart_items_insert_policy ON cart_items
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY cart_items_update_policy ON cart_items
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY cart_items_delete_policy ON cart_items
    FOR DELETE USING (auth.uid() = user_id);

-- Cart Coupons: Users can only access their own
CREATE POLICY cart_coupons_select_policy ON cart_coupons
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY cart_coupons_insert_policy ON cart_coupons
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY cart_coupons_delete_policy ON cart_coupons
    FOR DELETE USING (auth.uid() = user_id);

-- Orders: Users can only see their own orders
CREATE POLICY orders_select_policy ON orders
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY orders_insert_policy ON orders
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Order Items: Users can see items from their orders
CREATE POLICY order_items_select_policy ON order_items
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM orders WHERE orders.id = order_items.order_id AND orders.user_id = auth.uid())
    );

-- Coupon Interactions: Users can only access their own
CREATE POLICY coupon_interactions_select_policy ON coupon_interactions
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY coupon_interactions_insert_policy ON coupon_interactions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- User Preferences: Users can only access their own
CREATE POLICY user_preferences_select_policy ON user_preferences
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY user_preferences_insert_policy ON user_preferences
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_preferences_update_policy ON user_preferences
    FOR UPDATE USING (auth.uid() = user_id);

-- ============================================================================
-- D-12: INDEXES FOR NEW TABLES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_store_inventory_store_id ON store_inventory(store_id);
CREATE INDEX IF NOT EXISTS idx_store_inventory_product_id ON store_inventory(product_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_user_id ON cart_items(user_id);
CREATE INDEX IF NOT EXISTS idx_cart_items_store_id ON cart_items(store_id);
CREATE INDEX IF NOT EXISTS idx_cart_coupons_user_id ON cart_coupons(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_store_id ON orders(store_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_coupon_interactions_user_id ON coupon_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_coupon_interactions_coupon_id ON coupon_interactions(coupon_id);
CREATE INDEX IF NOT EXISTS idx_coupon_interactions_action ON coupon_interactions(action);
CREATE INDEX IF NOT EXISTS idx_coupons_discount_type ON coupons(discount_type);
CREATE INDEX IF NOT EXISTS idx_coupons_is_active ON coupons(is_active);

-- ============================================================================
-- TRIGGERS FOR updated_at
-- ============================================================================
CREATE TRIGGER trigger_store_inventory_updated_at
    BEFORE UPDATE ON store_inventory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_cart_items_updated_at
    BEFORE UPDATE ON cart_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
