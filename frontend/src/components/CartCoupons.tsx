import React, { useState } from 'react';
import { useCart } from '../contexts/CartContext';
import { Badge } from './ui/badge';
import { Ticket, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

interface CouponState {
  id: string;
  isLoading: boolean;
  error: string | null;
}

export function CartCoupons() {
  const {
    eligibleCoupons,
    ineligibleCoupons,
    addCoupon,
    removeCoupon,
    loading,
    setEligibleCoupons,
    setIneligibleCoupons
  } = useCart();

  // Local state for optimistic updates
  const [couponStates, setCouponStates] = useState<Record<string, CouponState>>({});

  const handleToggleCoupon = async (couponId: string, isSelected: boolean) => {
    // Prevent double-clicks
    if (couponStates[couponId]?.isLoading) {
      return;
    }

    // Update local state optimistically
    const originalCoupons = [...eligibleCoupons];
    const targetCoupon = eligibleCoupons.find(c => c.id === couponId);

    if (!targetCoupon) return;

    // Show loading state on this specific coupon
    setCouponStates(prev => ({
      ...prev,
      [couponId]: { id: couponId, isLoading: true, error: null }
    }));

    // Optimistic update: toggle the checkbox immediately
    const optimisticCoupons = eligibleCoupons.map(c =>
      c.id === couponId ? { ...c, is_selected: !isSelected } : c
    );
    setEligibleCoupons(optimisticCoupons);

    try {
      // Make API call
      if (isSelected) {
        await removeCoupon(couponId);
      } else {
        await addCoupon(couponId);
      }

      // Success: clear loading state (API response will update state properly)
      setCouponStates(prev => ({
        ...prev,
        [couponId]: { id: couponId, isLoading: false, error: null }
      }));

    } catch (error) {
      // Error: rollback to original state
      console.error('Error toggling coupon:', error);
      setEligibleCoupons(originalCoupons);

      // Show error state
      setCouponStates(prev => ({
        ...prev,
        [couponId]: {
          id: couponId,
          isLoading: false,
          error: 'Failed to apply coupon'
        }
      }));

      // Clear error after 3 seconds
      setTimeout(() => {
        setCouponStates(prev => ({
          ...prev,
          [couponId]: {
            id: couponId,
            isLoading: false,
            error: null
          }
        }));
      }, 3000);
    }
  };

  const getCouponState = (couponId: string) => {
    return couponStates[couponId] || { id: couponId, isLoading: false, error: null };
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
        {eligibleCoupons.map((coupon) => {
          const state = getCouponState(coupon.id);
          return (
            <div
              key={coupon.id}
              className={`flex items-start gap-2 p-2 border rounded-md transition-all ${
                coupon.is_selected
                  ? 'bg-green-50/50 border-green-200'
                  : 'bg-white border-gray-200'
              }`}
            >
              <div className="flex items-center">
                {state.isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                ) : (
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    checked={coupon.is_selected}
                    onChange={() => handleToggleCoupon(coupon.id, !!coupon.is_selected)}
                    disabled={state.isLoading}
                  />
                )}
              </div>

              <div className="flex-1 text-sm min-w-0">
                <p className={`font-medium ${
                  coupon.is_selected ? 'text-green-700' : 'text-gray-900'
                }`}>
                  {coupon.discount_details}
                </p>
                <p className="text-xs text-muted-foreground">
                  {coupon.type === 'frontstore' ? 'Basket-offers' : coupon.category_or_brand}
                </p>

                {state.error && (
                  <div className="flex items-center gap-1 text-xs text-red-500 mt-1">
                    <AlertCircle className="h-3 w-3" />
                    <span>{state.error}</span>
                  </div>
                )}
              </div>

              {coupon.is_selected && (
                <Badge variant="default" className="bg-green-600 text-[10px] h-5 shrink-0">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Applied
                </Badge>
              )}
            </div>
          );
        })}

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
