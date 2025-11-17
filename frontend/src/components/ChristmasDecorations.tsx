export function ChristmasDecorations() {
  return (
    <>
      {/* Winter Gradient Overlay */}
      <div className="fixed top-0 left-0 right-0 h-48 pointer-events-none z-0 bg-gradient-to-b from-sky-100/10 via-blue-50/5 to-transparent" />

      {/* Falling Snowflakes */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="snowflake absolute text-white/70"
            style={{
              left: `${Math.random() * 100}%`,
              fontSize: `${Math.random() * 10 + 10}px`,
              animationDelay: `${Math.random() * 10}s`,
              animationDuration: `${Math.random() * 10 + 10}s`,
            }}
          >
            ❄
          </div>
        ))}
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes snowfall {
          0% {
            transform: translateY(-10vh) translateX(0);
            opacity: 0;
          }
          10% {
            opacity: 1;
          }
          90% {
            opacity: 1;
          }
          100% {
            transform: translateY(110vh) translateX(50px);
            opacity: 0;
          }
        }

        .snowflake {
          animation: snowfall linear infinite;
          will-change: transform;
        }

        @keyframes gentle-glow {
          0%, 100% {
            filter: drop-shadow(0 0 2px rgba(255, 215, 0, 0.3));
          }
          50% {
            filter: drop-shadow(0 0 6px rgba(255, 215, 0, 0.5));
          }
        }

        .festive-glow {
          animation: gentle-glow 3s ease-in-out infinite;
        }
      `}</style>
    </>
  )
}
