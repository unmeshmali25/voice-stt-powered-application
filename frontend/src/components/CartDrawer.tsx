import React from 'react';
import { ShoppingCart } from 'lucide-react';
import { Button } from './ui/button';
import { useNavigate } from 'react-router-dom';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
} from './ui/sheet';
import { CartItem } from './CartItem';
import { CartCoupons } from './CartCoupons';
import { useCart } from '../contexts/CartContext';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';

export function CartDrawer() {
  const { items, itemCount, summary, clearCart, loading } = useCart();
  const navigate = useNavigate();

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="icon" className="relative">
          <ShoppingCart className="h-5 w-5" />
          {itemCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-2 -right-2 h-5 w-5 flex items-center justify-center rounded-full p-0 text-xs"
            >
              {itemCount}
            </Badge>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-md flex flex-col">
        <SheetHeader>
          <SheetTitle>Shopping Cart ({itemCount} items)</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto py-4">
          {items.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center space-y-2">
              <ShoppingCart className="h-12 w-12 text-muted-foreground" />
              <p className="text-lg font-medium">Your cart is empty</p>
              <p className="text-sm text-muted-foreground">
                Add items to get started
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((item) => (
                <CartItem key={item.cart_item_id} item={item} />
              ))}
            </div>
          )}
          
          {items.length > 0 && (
             <div className="mt-6">
                <CartCoupons />
             </div>
          )}
        </div>

        {items.length > 0 && (
          <div className="space-y-4 pt-4">
            <Separator />
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-sm">Subtotal</span>
                <span className="text-sm font-medium">
                  ${summary?.subtotal.toFixed(2)}
                </span>
              </div>
              {summary && summary.discount_total > 0 && (
                <div className="flex justify-between text-green-600">
                  <span className="text-sm">Savings</span>
                  <span className="text-sm font-medium">
                    -${summary.discount_total.toFixed(2)}
                  </span>
                </div>
              )}
              <div className="flex justify-between text-lg font-bold">
                <span>Total</span>
                <span>${summary?.final_total.toFixed(2)}</span>
              </div>
            </div>
            <SheetFooter className="flex-col gap-2 sm:flex-col">
              <Button className="w-full" size="lg" onClick={() => navigate('/checkout')}>
                Checkout
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => clearCart()}
                disabled={loading}
              >
                Clear Cart
              </Button>
            </SheetFooter>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
