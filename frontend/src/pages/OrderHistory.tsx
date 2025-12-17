import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api';
import { Order } from '../types/retail';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ArrowLeft, Loader2 } from 'lucide-react';

export function OrderHistory() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        const response = await apiFetch('/orders?limit=20');
        if (response.ok) {
          const data = await response.json();
          setOrders(data.orders);
        }
      } catch (error) {
        console.error('Failed to fetch orders:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchOrders();
  }, []);

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <div className="flex items-center gap-4 mb-8">
        <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-3xl font-bold">Order History</h1>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground text-lg mb-4">No orders found</p>
          <Button onClick={() => navigate('/')}>Start Shopping</Button>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <Card 
                key={order.id} 
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() => navigate(`/orders/${order.id}`)}
            >
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-lg">
                    Order #{order.id.slice(0, 8)}
                </CardTitle>
                <Badge variant={order.status === 'completed' ? 'default' : 'secondary'}>
                    {order.status || 'Completed'}
                </Badge>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                        <p className="text-muted-foreground">Date</p>
                        <p>{new Date(order.created_at).toLocaleDateString()}</p>
                    </div>
                     <div>
                        <p className="text-muted-foreground">Store</p>
                        <p>{order.store.name}</p>
                    </div>
                     <div>
                        <p className="text-muted-foreground">Items</p>
                        <p>{order.item_count} items</p>
                    </div>
                     <div className="text-right">
                        <p className="text-muted-foreground">Total</p>
                        <p className="font-bold">${order.final_total.toFixed(2)}</p>
                    </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
