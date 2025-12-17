import React from 'react';
import { Minus, Plus, Trash2 } from 'lucide-react';
import { CartItem as CartItemType } from '../types/retail';
import { useCart } from '../contexts/CartContext';
import { Button } from './ui/button';

interface CartItemProps {
  item: CartItemType;
}

export function CartItem({ item }: CartItemProps) {
  const { updateQuantity, removeItem, loading } = useCart();
  const { product, quantity, line_total } = item;

  const handleIncrement = () => {
    updateQuantity(item.cart_item_id, quantity + 1);
  };

  const handleDecrement = () => {
    if (quantity > 1) {
      updateQuantity(item.cart_item_id, quantity - 1);
    }
  };

  const handleRemove = () => {
    removeItem(item.cart_item_id);
  };

  return (
    <div className="flex gap-4 py-4 border-b">
      <div className="h-20 w-20 flex-shrink-0 overflow-hidden rounded-md border bg-white">
        <img
          src={product.imageUrl}
          alt={product.name}
          className="h-full w-full object-contain p-2"
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="300" viewBox="0 0 200 300"%3E%3Crect fill="%23ddd" width="200" height="300"/%3E%3Ctext fill="%23999" font-family="sans-serif" font-size="16" dy="10.5" font-weight="bold" x="50%25" y="50%25" text-anchor="middle"%3ENo Image%3C/text%3E%3C/svg%3E';
          }}
        />
      </div>

      <div className="flex flex-1 flex-col">
        <div className="flex justify-between text-base font-medium">
          <h3 className="line-clamp-2 text-sm">{product.name}</h3>
          <p className="ml-4">${line_total.toFixed(2)}</p>
        </div>
        <p className="mt-1 text-sm text-gray-500">{product.brand}</p>
        
        <div className="flex flex-1 items-end justify-between text-sm">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={handleDecrement}
              disabled={loading || quantity <= 1}
            >
              <Minus className="h-3 w-3" />
            </Button>
            <span className="w-8 text-center">{quantity}</span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={handleIncrement}
              disabled={loading}
            >
              <Plus className="h-3 w-3" />
            </Button>
          </div>

          <Button
            variant="ghost"
            size="sm"
            className="text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={handleRemove}
            disabled={loading}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            Remove
          </Button>
        </div>
      </div>
    </div>
  );
}
