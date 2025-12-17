import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../contexts/CartContext';
import { useStore } from '../contexts/StoreContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { Loader2, ArrowLeft } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { clearCurrentShoppingSession } from '../lib/shoppingSession';

export function Checkout() {
  const { items, summary, itemCount, clearCart } = useCart();
  const { selectedStore } = useStore();
  const navigate = useNavigate();
  const [placingOrder, setPlacingOrder] = useState(false);

  const handlePlaceOrder = async () => {
    if (!selectedStore) return;
    
    setPlacingOrder(true);
    try {
      const response = await apiFetch('/api/orders', {
        method: 'POST',
      });

      if (response.ok) {
        const data = await response.json();
        // Clear cart is usually handled by backend or we do it here
        await clearCart();
        // Rotate shopping session after successful checkout
        await clearCurrentShoppingSession();
        navigate('/order-confirmation', { state: { order: data.order } });
      } else {
        const error = await response.json();
        alert(`Failed to place order: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error placing order:', error);
      alert('An error occurred while placing the order.');
    } finally {
      setPlacingOrder(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="container mx-auto p-6 flex flex-col items-center justify-center min-h-[50vh]">
        <h2 className="text-2xl font-bold mb-4">Your cart is empty</h2>
        <Button onClick={() => navigate('/')}>Continue Shopping</Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <Button variant="ghost" className="mb-6" onClick={() => navigate('/')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Back to Shopping
      </Button>
      
      <h1 className="text-3xl font-bold mb-8">Checkout</h1>
      
      <div className="grid gap-8 md:grid-cols-3">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Review Order</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {items.map((item) => (
                <div key={item.cart_item_id} className="flex gap-4">
                  <div className="h-16 w-16 overflow-hidden rounded-md border bg-white flex-shrink-0">
                    <img
                      src={item.product.imageUrl}
                      alt={item.product.name}
                      className="h-full w-full object-contain p-1"
                    />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-medium">{item.product.name}</h4>
                    <p className="text-sm text-muted-foreground">Qty: {item.quantity}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">${item.line_total.toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground">${item.product.price} / unit</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
          
          <Card>
             <CardHeader>
              <CardTitle>Pickup Store</CardTitle>
            </CardHeader>
            <CardContent>
                <p className="font-medium">{selectedStore?.name}</p>
                <p className="text-sm text-muted-foreground">Items will be ready for pickup in 2 hours.</p>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card className="sticky top-24">
            <CardHeader>
              <CardTitle>Order Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between text-sm">
                <span>Subtotal ({itemCount} items)</span>
                <span>${summary?.subtotal.toFixed(2)}</span>
              </div>
              
              {summary && summary.discount_total > 0 && (
                 <div className="flex justify-between text-sm text-green-600">
                  <span>Savings</span>
                  <span>-${summary.discount_total.toFixed(2)}</span>
                </div>
              )}
              
              <Separator />
              
              <div className="flex justify-between font-bold text-lg">
                <span>Total</span>
                <span>${summary?.final_total.toFixed(2)}</span>
              </div>
            </CardContent>
            <CardFooter>
              <Button 
                className="w-full" 
                size="lg" 
                onClick={handlePlaceOrder}
                disabled={placingOrder}
              >
                {placingOrder ? (
                    <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Placing Order...
                    </>
                ) : (
                    `Place Order`
                )}
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    </div>
  );
}
