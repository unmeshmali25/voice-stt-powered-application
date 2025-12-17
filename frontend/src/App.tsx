import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext'
import { StoreProvider } from './contexts/StoreContext'
import { CartProvider } from './contexts/CartContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { MainLayout } from './components/MainLayout'
import { MobileLayout } from './components/MobileLayout'
import { useIsMobile } from './hooks/use-mobile'
import { Checkout } from './pages/Checkout'
import { OrderConfirmation } from './pages/OrderConfirmation'
import { OrderHistory } from './pages/OrderHistory'
import { OrderDetail } from './pages/OrderDetail'

function App() {
  const isMobile = useIsMobile()

  return (
    <Router>
      <AuthProvider>
        <StoreProvider>
          <CartProvider>
            <Routes>
              <Route path="/" element={
                <ProtectedRoute>
                  {isMobile ? <MobileLayout /> : <MainLayout />}
                </ProtectedRoute>
              } />
              <Route path="/checkout" element={
                <ProtectedRoute>
                  <Checkout />
                </ProtectedRoute>
              } />
              <Route path="/order-confirmation" element={
                <ProtectedRoute>
                  <OrderConfirmation />
                </ProtectedRoute>
              } />
              <Route path="/orders" element={
                <ProtectedRoute>
                  <OrderHistory />
                </ProtectedRoute>
              } />
              <Route path="/orders/:orderId" element={
                <ProtectedRoute>
                  <OrderDetail />
                </ProtectedRoute>
              } />
            </Routes>
          </CartProvider>
        </StoreProvider>
      </AuthProvider>
    </Router>
  )
}

export default App
