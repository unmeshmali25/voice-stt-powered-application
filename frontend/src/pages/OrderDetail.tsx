import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import { Order } from '../types/retail';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { ArrowLeft, Loader2 } from 'lucide-react';

export function OrderDetail() {
  const { orderId } = useParams<{ orderId: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchOrder = async () => {
      try {
        const response = await apiFetch(`/orders/${orderId}`);
        if (response.ok) {
          const data = await response.json();
          setOrder(data.order);
        } else {
             alert("Order not found");
             navigate('/orders');
        }
      } catch (error) {
        console.error('Failed to fetch order:', error);
      } finally {
        setLoading(false);
      }
    };

    if (orderId) {
        fetchOrder();
    }
  }, [orderId, navigate]);

  if (loading) {
     return (
        <div className="flex justify-center items-center h-screen">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      );
  }

  if (!order) return null;

  return (
    <div className="container mx-auto p-6 max-w-3xl">
       <div className="flex items-center gap-4 mb-8">
        <Button variant="ghost" size="icon" onClick={() => navigate('/orders')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
             <h1 className="text-2xl font-bold">Order Details</h1>
             <p className="text-sm text-muted-foreground">#{order.id}</p>
        </div>
         <Badge variant="outline" className="text-lg px-4 py-1">
             {order.status || 'Completed'}
         </Badge>
      </div>

      <div className="space-y-6">
        <Card>
            <CardHeader>
                <CardTitle>Items</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {order.items.map((item) => (
                    <div key={item.id} className="flex justify-between items-start">
                        <div>
                            <p className="font-medium">{item.product_name}</p>
                            <p className="text-sm text-muted-foreground">Qty: {item.quantity} x ${item.unit_price}</p>
                            {item.discount_amount > 0 && (
                                <p className="text-xs text-green-600">Saved: ${item.discount_amount.toFixed(2)}</p>
                            )}
                        </div>
                        <p className="font-medium">${item.line_total.toFixed(2)}</p>
                    </div>
                ))}
            </CardContent>
        </Card>

        <Card>
            <CardHeader>
                <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
                 <div className="flex justify-between text-sm">
                    <span>Subtotal</span>
                    <span>${order.totals.subtotal.toFixed(2)}</span>
                </div>
                 {order.totals.discount_total > 0 && (
                    <div className="flex justify-between text-sm text-green-600">
                        <span>Total Savings</span>
                        <span>-${order.totals.discount_total.toFixed(2)}</span>
                    </div>
                )}
                 <Separator className="my-2" />
                 <div className="flex justify-between font-bold text-lg">
                    <span>Total Paid</span>
                    <span>${order.totals.final_total.toFixed(2)}</span>
                </div>
            </CardContent>
        </Card>

        <Card>
            <CardHeader>
                <CardTitle>Store Information</CardTitle>
            </CardHeader>
            <CardContent>
                <p className="font-medium">{order.store.name}</p>
                <p className="text-sm text-muted-foreground">Order Date: {new Date(order.created_at).toLocaleString()}</p>
            </CardContent>
        </Card>
      </div>
    </div>
  );
}
