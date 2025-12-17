import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiFetch } from '../lib/api';
import { Store } from '../types/retail';
import { useAuth } from '../hooks/useAuth';

interface StoreContextType {
  selectedStore: Store | null;
  stores: Store[];
  loading: boolean;
  setStore: (storeId: string) => Promise<void>;
  refreshStores: () => Promise<void>;
}

const StoreContext = createContext<StoreContextType | undefined>(undefined);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const { session } = useAuth();

  const fetchStores = async () => {
    try {
      const response = await apiFetch('/stores');
      if (response.ok) {
        const data = await response.json();
        setStores(data.stores);
      }
    } catch (error) {
      console.error('Failed to fetch stores:', error);
    }
  };

  const fetchUserStore = async () => {
    if (!session) return;
    try {
      const response = await apiFetch('/user/store');
      if (response.ok) {
        const data = await response.json();
        if (data.has_selection && data.store) {
          setSelectedStore(data.store);
        } else {
          setSelectedStore(null);
        }
      }
    } catch (error) {
      console.error('Failed to fetch user store:', error);
    } finally {
      setLoading(false);
    }
  };

  const setStore = async (storeId: string) => {
    try {
      const response = await apiFetch('/user/store', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ store_id: storeId }),
      });

      if (response.ok) {
        const data = await response.json();
        setSelectedStore(data.store);
        // If cart was cleared, we might want to trigger a cart refresh here
        // or let the CartContext handle it via a shared event or re-fetch
      }
    } catch (error) {
      console.error('Failed to set store:', error);
      throw error;
    }
  };

  useEffect(() => {
    fetchStores();
  }, []);

  useEffect(() => {
    if (session) {
      fetchUserStore();
    } else {
      setLoading(false);
      setSelectedStore(null);
    }
  }, [session]);

  return (
    <StoreContext.Provider
      value={{
        selectedStore,
        stores,
        loading,
        setStore,
        refreshStores: fetchStores,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const context = useContext(StoreContext);
  if (context === undefined) {
    throw new Error('useStore must be used within a StoreProvider');
  }
  return context;
}
