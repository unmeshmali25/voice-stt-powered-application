import { AuthProvider } from './contexts/AuthContext'
import { ProtectedRoute } from './components/ProtectedRoute'
import { MainLayout } from './components/MainLayout'
import { MobileLayout } from './components/MobileLayout'
import { useIsMobile } from './hooks/use-mobile'

function App() {
  const isMobile = useIsMobile()

  return (
    <AuthProvider>
      <ProtectedRoute>
        {isMobile ? <MobileLayout /> : <MainLayout />}
      </ProtectedRoute>
    </AuthProvider>
  )
}

export default App
