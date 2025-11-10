import { ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { AuthPage } from './AuthPage'
import { isSupabaseConfigured } from '@/lib/supabase'

interface ProtectedRouteProps {
  children: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading } = useAuth()

  // Show configuration error if Supabase is not configured
  if (!isSupabaseConfigured) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <div className="max-w-md w-full space-y-4">
          <div className="p-4 border border-yellow-200 bg-yellow-50 rounded-lg">
            <h2 className="text-lg font-semibold text-yellow-900 mb-2">
              Configuration Required
            </h2>
            <p className="text-sm text-yellow-800 mb-4">
              Supabase environment variables are not configured. Please create a <code className="bg-yellow-100 px-1 rounded">.env</code> file in the <code className="bg-yellow-100 px-1 rounded">frontend/</code> directory with:
            </p>
            <pre className="text-xs bg-yellow-100 p-3 rounded overflow-x-auto">
{`VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key`}
            </pre>
            <p className="text-xs text-yellow-700 mt-3">
              See <code className="bg-yellow-100 px-1 rounded">AUTH_SETUP.md</code> for detailed instructions.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
  }

  return <>{children}</>
}

