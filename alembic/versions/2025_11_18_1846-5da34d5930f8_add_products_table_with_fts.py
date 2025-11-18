"""add_products_table_with_fts

Revision ID: 5da34d5930f8
Revises: 
Create Date: 2025-11-18 18:46:38.953515

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5da34d5930f8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create products table
    op.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            image_url TEXT NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            rating DECIMAL(2, 1),
            review_count INTEGER DEFAULT 0,
            category VARCHAR(255),
            brand VARCHAR(255),
            promo_text VARCHAR(255),
            in_stock BOOLEAN DEFAULT true,
            text_vector tsvector,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes for products table
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_text_vector ON products USING GIN(text_vector)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(in_stock)")

    # Create function to automatically update text_vector for products
    op.execute("""
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
        $$ LANGUAGE plpgsql
    """)

    # Create trigger for text_vector auto-update
    op.execute("DROP TRIGGER IF EXISTS trigger_products_text_vector_update ON products")
    op.execute("""
        CREATE TRIGGER trigger_products_text_vector_update
            BEFORE INSERT OR UPDATE OF name, description, category, brand ON products
            FOR EACH ROW
            EXECUTE FUNCTION products_text_vector_update()
    """)

    # Create trigger for updated_at auto-update (assumes update_updated_at_column function exists)
    op.execute("DROP TRIGGER IF EXISTS trigger_products_updated_at ON products")
    op.execute("""
        CREATE TRIGGER trigger_products_updated_at
            BEFORE UPDATE ON products
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    # Drop triggers first
    op.execute("DROP TRIGGER IF EXISTS trigger_products_updated_at ON products")
    op.execute("DROP TRIGGER IF EXISTS trigger_products_text_vector_update ON products")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS products_text_vector_update()")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_products_in_stock")
    op.execute("DROP INDEX IF EXISTS idx_products_text_vector")
    op.execute("DROP INDEX IF EXISTS idx_products_brand")
    op.execute("DROP INDEX IF EXISTS idx_products_category")

    # Drop table
    op.execute("DROP TABLE IF EXISTS products CASCADE")
