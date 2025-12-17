import React, { useState } from 'react';
import { useCart } from '../contexts/CartContext';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox'; // Need to check if checkbox exists
import { Badge } from './ui/badge';
import { Ticket } from 'lucide-react';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './ui/accordion'; // Need to check if accordion exists

export function CartCoupons() {
  const { eligibleCoupons, ineligibleCoupons, addCoupon, removeCoupon, loading } = useCart();

  const handleToggleCoupon = async (couponId: string, isSelected: boolean) => {
    if (isSelected) {
      await removeCoupon(couponId);
    } else {
      await addCoupon(couponId);
    }
  };

  if (eligibleCoupons.length === 0 && ineligibleCoupons.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 font-medium text-sm">
        <Ticket className="h-4 w-4" />
        <span>Coupons & Offers</span>
      </div>

      <div className="space-y-2">
        {eligibleCoupons.map((coupon) => (
          <div key={coupon.id} className="flex items-start gap-2 p-2 border rounded-md bg-green-50/50 border-green-200">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              checked={coupon.is_selected}
              onChange={() => handleToggleCoupon(coupon.id, !!coupon.is_selected)}
              disabled={loading}
            />
            <div className="flex-1 text-sm">
               <p className="font-medium text-green-700">{coupon.discount_details}</p>
               <p className="text-xs text-muted-foreground">{coupon.type === 'frontstore' ? 'Store Offer' : coupon.category_or_brand}</p>
            </div>
            {coupon.is_selected && <Badge variant="default" className="bg-green-600 text-[10px] h-5">Applied</Badge>}
          </div>
        ))}
        
        {ineligibleCoupons.length > 0 && (
            <div className="pt-2">
                <p className="text-xs text-muted-foreground mb-2">Available but not applicable:</p>
                {ineligibleCoupons.map((coupon) => (
                    <div key={coupon.id} className="flex items-start gap-2 p-2 border rounded-md bg-gray-50 opacity-60">
                        <div className="flex-1 text-sm">
                             <p className="font-medium">{coupon.discount_details}</p>
                             <p className="text-xs text-red-500">{coupon.ineligible_reason || 'Requirements not met'}</p>
                        </div>
                    </div>
                ))}
            </div>
        )}
      </div>
    </div>
  );
}
