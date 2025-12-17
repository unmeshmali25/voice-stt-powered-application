import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { CheckCircle } from 'lucide-react';

export function OrderConfirmation() {
  const location = useLocation();
  const navigate = useNavigate();
  const order = location.state?.order;

  if (!order) {
    return (
      <div className="container mx-auto p-6 flex flex-col items-center justify-center min-h-[50vh]">
        <h2 className="text-2xl font-bold mb-4">Order not found</h2>
        <Button onClick={() => navigate('/')}>Back to Home</Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-2xl text-center">
      <div className="flex justify-center mb-6">
        <CheckCircle className="h-24 w-24 text-green-500" />
      </div>
      
      <h1 className="text-3xl font-bold mb-2">Order Confirmed!</h1>
      <p className="text-muted-foreground mb-8">
        Thank you for your purchase. Your order #{order.id.slice(0, 8)} has been placed.
      </p>
      
      <Card className="text-left mb-8">
        <CardHeader>
          <CardTitle>Order Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
            <div className="flex justify-between">
                <span className="text-muted-foreground">Store:</span>
                <span className="font-medium">{order.store.name}</span>
            </div>
             <div className="flex justify-between">
                <span className="text-muted-foreground">Total:</span>
                <span className="font-bold">${order.totals.final_total.toFixed(2)}</span>
            </div>
             <div className="flex justify-between">
                <span className="text-muted-foreground">Date:</span>
                <span>{new Date(order.created_at).toLocaleDateString()}</span>
            </div>
        </CardContent>
      </Card>

      <div className="flex gap-4 justify-center">
        <Button variant="outline" onClick={() => navigate('/orders')}>
          View Order History
        </Button>
        <Button onClick={() => navigate('/')}>
          Continue Shopping
        </Button>
      </div>
    </div>
  );
}
