import { useState, useEffect, useCallback, useRef } from 'react'
import { Coupon } from '../types/coupon'
import { Product } from '../types/product'
import { useAuth } from './useAuth'
import { supabase } from '../lib/supabase'
import { apiFetch } from '../lib/api'

// Mock data
const mockFrontstoreCoupons: Coupon[] = [
  {
    id: '1',
    type: 'frontstore',
    discountDetails: '2% off entire purchase',
    expirationDate: '2025-12-31',
    terms: 'Valid on all items. Cannot be combined with other offers.'
  },
  {
    id: '2',
    type: 'frontstore',
    discountDetails: '$2 off on $20 purchase',
    expirationDate: '2025-11-30',
    terms: 'Minimum purchase of $20 required.'
  },
  {
    id: '3',
    type: 'frontstore',
    discountDetails: '5% off orders over $50',
    expirationDate: '2025-12-15',
  },
]

const mockCategoryBrandCoupons: Coupon[] = [
  {
    id: '4',
    type: 'category',
    discountDetails: '20% off',
    categoryOrBrand: 'Beauty Products',
    expirationDate: '2025-11-25',
    terms: 'Excludes premium brands.'
  },
  {
    id: '5',
    type: 'brand',
    discountDetails: 'Buy 2 Get 1 Free',
    categoryOrBrand: 'Coca-Cola',
    expirationDate: '2025-12-10',
  },
  {
    id: '6',
    type: 'category',
    discountDetails: '$5 off',
    categoryOrBrand: 'Dairy Products',
    expirationDate: '2025-11-28',
  },
]

const mockProducts: Product[] = [
  {
    id: '1',
    name: 'CVS Durable Nitrile Exam Gloves',
    imageUrl: 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400',
    price: 15.79,
    rating: 5,
    reviewCount: 205,
    category: 'Health',
    inStock: true
  },
  {
    id: '2',
    name: 'CVS Extra Strength Acetaminophen Pain Reliever, 500 mg',
    imageUrl: 'https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=400',
    price: 10.49,
    rating: 5,
    reviewCount: 345,
    category: 'Health',
    inStock: true
  },
  {
    id: '3',
    name: "Nature's Bounty Magnesium Tablets 500mg",
    imageUrl: 'https://images.unsplash.com/photo-1550572017-4340e44c1f6a?w=400',
    price: 19.49,
    rating: 5,
    reviewCount: 162,
    promoText: 'Buy 1, Get 1 Free',
    category: 'Vitamins',
    inStock: true
  },
  {
    id: '4',
    name: 'One+other Premium Cotton Rounds',
    imageUrl: 'https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400',
    price: 4.19,
    rating: 5,
    reviewCount: 273,
    promoText: 'Buy 2, Get 1 Free',
    category: 'Beauty',
    inStock: true
  },
]

export function useStoreData() {
  const [transcript, setTranscript] = useState<string>('')
  const [products, setProducts] = useState<Product[]>([])
  const [frontstoreCoupons, setFrontstoreCoupons] = useState<Coupon[]>([])
  const [categoryBrandCoupons, setCategoryBrandCoupons] = useState<Coupon[]>([])
  const [isLoadingProducts, setIsLoadingProducts] = useState(false)
  const [isLoadingCoupons, setIsLoadingCoupons] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [isARMode, setIsARMode] = useState(false)
  const [isWalletView, setIsWalletView] = useState(true)
  const [categoryBrandVisibleCount, setCategoryBrandVisibleCount] = useState(5)
  const { user, signOut } = useAuth()
  const searchDebounceRef = useRef<NodeJS.Timeout | null>(null)

  const loadRecommendations = useCallback(async () => {
    setIsLoadingProducts(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        console.log('No session, showing default products')
        setProducts(mockProducts.slice(0, 5))
        return
      }

      const response = await apiFetch('/api/products/recommendations?limit=5', {
        method: 'GET'
      })

      if (response.ok) {
        const data = await response.json()
        console.log(`Loaded ${data.count} recommendations (personalized=${data.personalized})`)
        const transformedProducts = data.products.map((p: any) => ({
          id: p.id,
          name: p.name,
          description: p.description,
          imageUrl: p.imageUrl,
          price: p.price,
          rating: p.rating,
          reviewCount: p.reviewCount,
          category: p.category,
          brand: p.brand,
          promoText: p.promoText,
          inStock: p.inStock
        }))
        setProducts(transformedProducts)
      } else {
        console.log('Recommendations API failed, using mock data')
        setProducts(mockProducts.slice(0, 5))
      }
    } catch (error) {
      console.error('Failed to load recommendations:', error)
      setProducts(mockProducts.slice(0, 5))
    } finally {
      setIsLoadingProducts(false)
    }
  }, [])

  const loadWalletCoupons = useCallback(async () => {
    setIsLoadingCoupons(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        console.log('No session, cannot load wallet coupons')
        setFrontstoreCoupons([])
        setCategoryBrandCoupons([])
        return
      }

      const response = await apiFetch('/api/coupons/wallet', {
        method: 'GET'
      })

      if (response.ok) {
        const data = await response.json()
        console.log(`Loaded wallet: ${data.frontstore.length} frontstore, ${data.categoryBrand.length} category/brand`)

        const transformFn = (c: any) => ({
          id: c.id,
          type: c.type,
          discountDetails: c.discount_details,
          categoryOrBrand: c.category_or_brand,
          expirationDate: c.expiration_date,
          terms: c.terms
        })

        setFrontstoreCoupons(data.frontstore.map(transformFn))
        setCategoryBrandCoupons(data.categoryBrand.map(transformFn))
      } else {
        console.error('Failed to load wallet coupons')
        setFrontstoreCoupons([])
        setCategoryBrandCoupons([])
      }
    } catch (error) {
      console.error('Error loading wallet coupons:', error)
      setFrontstoreCoupons([])
      setCategoryBrandCoupons([])
    } finally {
      setIsLoadingCoupons(false)
    }
  }, [])

  const syncUserProfile = useCallback(async () => {
    try {
      const response = await apiFetch('/api/auth/me', {
        method: 'GET'
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        console.warn('User profile sync failed:', {
          status: response.status,
          error: errorData.detail || 'Unknown error'
        })
        return
      }

      const userData = await response.json()
      console.log('User profile synced successfully:', {
        id: userData.id,
        email: userData.email,
        created_at: userData.created_at
      })
    } catch (error) {
      console.error('Failed to sync user profile:', error)
    }
  }, [])

  useEffect(() => {
    const initializeUser = async () => {
      try {
        await syncUserProfile()
        await Promise.all([
          loadWalletCoupons(),
          loadRecommendations()
        ])
      } catch (error) {
        console.error('Startup initialization had errors:', error)
      }
    }

    initializeUser()
  }, [syncUserProfile, loadRecommendations, loadWalletCoupons])

  const handleTranscriptChange = useCallback(async (newTranscript: string) => {
    setTranscript(newTranscript)

    // Clear any pending debounced search
    if (searchDebounceRef.current) {
      clearTimeout(searchDebounceRef.current)
      searchDebounceRef.current = null
    }

    // Empty transcript: reset immediately (no debounce)
    if (!newTranscript.trim()) {
      setIsWalletView(true)
      setCategoryBrandVisibleCount(5)
      setHasSearched(false)
      await loadWalletCoupons()
      await loadRecommendations()
      return
    }

    // Debounce actual search by 300ms
    searchDebounceRef.current = setTimeout(async () => {
      setIsWalletView(false)
      setCategoryBrandVisibleCount(4)
      setHasSearched(true)

      const { data: { session } } = await supabase.auth.getSession()

      if (!session?.access_token) {
        console.error('No authentication token available')
        return
      }

      // Run product and coupon searches in parallel
      setIsLoadingProducts(true)
      setIsLoadingCoupons(true)

      try {
        const [productsResponse, couponsResponse] = await Promise.all([
          apiFetch('/api/products/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: newTranscript, limit: 50 })
          }),
          apiFetch('/api/coupons/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: newTranscript })
          })
        ])

        // Process products
        if (productsResponse.ok) {
          const productsData = await productsResponse.json()
          const transformedProducts = productsData.products.map((p: any) => ({
            id: p.id,
            name: p.name,
            description: p.description,
            imageUrl: p.imageUrl,
            price: p.price,
            rating: p.rating,
            reviewCount: p.reviewCount,
            category: p.category,
            brand: p.brand,
            promoText: p.promoText,
            inStock: p.inStock
          }))
          setProducts(transformedProducts)
        }

        // Process coupons
        if (couponsResponse.ok) {
          const couponsData = await couponsResponse.json()
          const transformedCoupons = couponsData.results.map((c: any) => ({
            id: c.id,
            type: c.type,
            discountDetails: c.discount_details || c.discountDetails,
            categoryOrBrand: c.category_or_brand || c.categoryOrBrand,
            expirationDate: c.expiration_date || c.expirationDate,
            terms: c.terms
          }))

          const frontstore = transformedCoupons.filter((c: Coupon) => c.type === 'frontstore')
          const categoryBrand = transformedCoupons.filter((c: Coupon) => c.type !== 'frontstore')

          setFrontstoreCoupons(frontstore)
          setCategoryBrandCoupons(categoryBrand)
        }
      } catch (error) {
        console.error('Search failed:', error)
      } finally {
        setIsLoadingProducts(false)
        setIsLoadingCoupons(false)
      }
    }, 300)
  }, [loadRecommendations, loadWalletCoupons])

  const handleLoadMoreCoupons = useCallback(() => {
    setCategoryBrandVisibleCount(prev => prev + 10)
  }, [])

  const toggleARMode = useCallback(() => {
    setIsARMode(prev => !prev)
  }, [])

  const handleARSearch = useCallback(async (query: string): Promise<Coupon[]> => {
    const { data: { session } } = await supabase.auth.getSession()

    if (!session?.access_token) {
      console.error('No authentication token available')
      return []
    }

    try {
      const couponsResponse = await apiFetch('/api/coupons/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question: query })
      })

      if (couponsResponse.ok) {
        const couponsData = await couponsResponse.json()
        const transformedCoupons = couponsData.results.map((c: any) => ({
          id: c.id,
          type: c.type,
          discountDetails: c.discount_details || c.discountDetails,
          categoryOrBrand: c.category_or_brand || c.categoryOrBrand,
          expirationDate: c.expiration_date || c.expirationDate,
          terms: c.terms
        }))

        return transformedCoupons
      }
    } catch (error) {
      console.error('AR coupon search failed:', error)
    }

    return []
  }, [])

  // Cleanup debounce timeout on unmount
  useEffect(() => {
    return () => {
      if (searchDebounceRef.current) {
        clearTimeout(searchDebounceRef.current)
      }
    }
  }, [])

  return {
    transcript,
    products,
    frontstoreCoupons,
    categoryBrandCoupons,
    isLoadingProducts,
    isLoadingCoupons,
    hasSearched,
    isARMode,
    isWalletView,
    categoryBrandVisibleCount,
    user,
    signOut,
    handleTranscriptChange,
    handleLoadMoreCoupons,
    toggleARMode,
    handleARSearch,
    mockProducts // Exporting mockProducts in case it's needed for skeletons or fallbacks
  }
}