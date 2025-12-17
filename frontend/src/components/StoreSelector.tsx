import React, { useState } from 'react';
import { useStore } from '../contexts/StoreContext';
import { useCart } from '../contexts/CartContext';
import { Button } from './ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { MapPin } from 'lucide-react';
import { cn } from '../lib/utils';

export function StoreSelector({ className }: { className?: string }) {
  const { selectedStore, stores, setStore, loading } = useStore();
  const { itemCount, clearCart } = useCart();
  const [showDialog, setShowDialog] = useState(false);
  const [pendingStoreId, setPendingStoreId] = useState<string | null>(null);

  const handleStoreChange = async (storeId: string) => {
    // If cart has items and we are changing store, warn user
    if (selectedStore && selectedStore.id !== storeId && itemCount > 0) {
      setPendingStoreId(storeId);
      setShowDialog(true);
    } else {
      await setStore(storeId);
    }
  };

  const confirmStoreChange = async () => {
    if (pendingStoreId) {
      await clearCart();
      await setStore(pendingStoreId);
      setShowDialog(false);
      setPendingStoreId(null);
    }
  };

  if (loading) {
    return (
      <Button variant="outline" size="sm" disabled className={className}>
        <MapPin className="mr-2 h-4 w-4" />
        Loading...
      </Button>
    );
  }

  return (
    <>
      <Select
        value={selectedStore?.id || ''}
        onValueChange={handleStoreChange}
      >
        <SelectTrigger className={cn("w-[180px]", className)}>
          <MapPin className="mr-2 h-4 w-4" />
          <SelectValue placeholder="Select a store" />
        </SelectTrigger>
        <SelectContent>
          {stores.length === 0 ? (
             <div className="p-2 text-sm text-muted-foreground text-center">No stores available</div>
          ) : (
            stores.map((store) => (
              <SelectItem key={store.id} value={store.id}>
                {store.name}
              </SelectItem>
            ))
          )}
        </SelectContent>
      </Select>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Store?</DialogTitle>
            <DialogDescription>
              Changing your store will clear your current cart. Are you sure you want to proceed?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmStoreChange}>
              Change Store & Clear Cart
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
