-- PostgreSQL Schema for VoiceOffers Coupon Platform
-- Full-text search with tsvector and Supabase authentication

-- Enable pg_trgm extension for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable UUID extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop old tables if they exist
DROP TABLE IF EXISTS pages CASCADE;
DROP TABLE IF EXISTS manuals CASCADE;

-- Users table (synced with Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,  -- Matches Supabase auth.users.id
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User attributes for dynamic coupon matching
CREATE TABLE IF NOT EXISTS user_attributes (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attribute_key VARCHAR(100) NOT NULL,  -- e.g., 'location', 'age_group', 'purchase_category'
    attribute_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, attribute_key)
);

-- Coupons master table
CREATE TABLE IF NOT EXISTS coupons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(50) NOT NULL CHECK (type IN ('frontstore', 'category', 'brand')),
    discount_details TEXT NOT NULL,
    category_or_brand VARCHAR(255),  -- Required for 'category' and 'brand' types
    expiration_date TIMESTAMP NOT NULL,
    terms TEXT,
    text_vector tsvector,  -- Full-text search vector (auto-generated)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-Coupon assignment (many-to-many)
CREATE TABLE IF NOT EXISTS user_coupons (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    eligible_until TIMESTAMP,  -- NULL = no expiration on assignment
    UNIQUE(user_id, coupon_id)
);

-- Coupon usage tracking
CREATE TABLE IF NOT EXISTS coupon_usage (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    redeemed_at TIMESTAMP,  -- NULL = viewed but not redeemed
    redemption_code VARCHAR(50),
    UNIQUE(user_id, coupon_id, viewed_at)
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    image_url TEXT NOT NULL,  -- URL to product image
    price DECIMAL(10, 2) NOT NULL,
    rating DECIMAL(2, 1),  -- e.g., 4.5
    review_count INTEGER DEFAULT 0,
    category VARCHAR(255),  -- e.g., "Beauty Products", "Health", "Personal Care"
    brand VARCHAR(255),
    promo_text VARCHAR(255),  -- e.g., "Buy 1, Get 1 Free"
    in_stock BOOLEAN DEFAULT true,
    text_vector tsvector,  -- Full-text search vector (auto-generated)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_attributes_user_id ON user_attributes(user_id);
CREATE INDEX IF NOT EXISTS idx_coupons_type ON coupons(type);
CREATE INDEX IF NOT EXISTS idx_coupons_expiration ON coupons(expiration_date);
CREATE INDEX IF NOT EXISTS idx_coupons_text_vector ON coupons USING GIN(text_vector);
CREATE INDEX IF NOT EXISTS idx_user_coupons_user_id ON user_coupons(user_id);
CREATE INDEX IF NOT EXISTS idx_user_coupons_coupon_id ON user_coupons(coupon_id);
CREATE INDEX IF NOT EXISTS idx_coupon_usage_user_id ON coupon_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_coupon_usage_coupon_id ON coupon_usage(coupon_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_text_vector ON products USING GIN(text_vector);
CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(in_stock);

-- Function to automatically update text_vector for coupons
CREATE OR REPLACE FUNCTION coupons_text_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.text_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.discount_details, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.category_or_brand, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.terms, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before INSERT or UPDATE
DROP TRIGGER IF EXISTS trigger_coupons_text_vector_update ON coupons;
CREATE TRIGGER trigger_coupons_text_vector_update
    BEFORE INSERT OR UPDATE OF discount_details, category_or_brand, terms ON coupons
    FOR EACH ROW
    EXECUTE FUNCTION coupons_text_vector_update();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS trigger_users_updated_at ON users;
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_coupons_updated_at ON coupons;
CREATE TRIGGER trigger_coupons_updated_at
    BEFORE UPDATE ON coupons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to automatically update text_vector for products
CREATE OR REPLACE FUNCTION products_text_vector_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.text_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.category, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.brand, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before INSERT or UPDATE
DROP TRIGGER IF EXISTS trigger_products_text_vector_update ON products;
CREATE TRIGGER trigger_products_text_vector_update
    BEFORE INSERT OR UPDATE OF name, description, category, brand ON products
    FOR EACH ROW
    EXECUTE FUNCTION products_text_vector_update();

DROP TRIGGER IF EXISTS trigger_products_updated_at ON products;
CREATE TRIGGER trigger_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
